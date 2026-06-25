"""
OpenAI dense embedder.

Drop-in replacement for DenseEmbedder (sentence-transformers). Produces
L2-normalised float32 vectors suitable for COSINE / dot-product similarity
in Qdrant. Integrates with the project's EmbeddingCache so repeated texts
are not re-embedded across ingestions.

Default model: text-embedding-3-small (1536 dims). Multilingual.
"""
from __future__ import annotations

from typing import Optional

import numpy as np

from src.cache_manager import get_cache
from src.config import DENSE_MODEL, DENSE_VECTOR_SIZE, OPENAI_API_KEY

try:
    from openai import OpenAI, OpenAIError
except ImportError as _exc:  # pragma: no cover
    raise ImportError(
        "The 'openai' package is required. Install it with: pip install openai"
    ) from _exc


# Keep well under OpenAI's per-request limits and avoid token-ceiling errors
# when chunks are large.
_OPENAI_BATCH_SIZE = 32


class OpenAIEmbedder:
    """
    OpenAI embeddings with disk cache.

    Parameters
    ----------
    model_name : OpenAI embedding model id (e.g. "text-embedding-3-small").
    cache      : EmbeddingCache instance (uses global default if None).
    """

    def __init__(
        self,
        model_name: str = DENSE_MODEL,
        cache=None,
    ) -> None:
        self.model_name = model_name
        self._cache = cache or get_cache()
        self._client: Optional[OpenAI] = None

    def _get_client(self) -> OpenAI:
        if self._client is None:
            if not OPENAI_API_KEY:
                raise RuntimeError(
                    "OPENAI_API_KEY is not configured. Set it in Qdrant/.env "
                    "before ingesting or searching."
                )
            self._client = OpenAI(api_key=OPENAI_API_KEY, timeout=60)
        return self._client

    @staticmethod
    def _l2_normalise(vec: np.ndarray) -> np.ndarray:
        norm = float(np.linalg.norm(vec))
        if norm == 0.0:
            return vec.astype(np.float32, copy=False)
        return (vec / norm).astype(np.float32, copy=False)

    def _call_openai(self, texts: list[str]) -> list[np.ndarray]:
        """Call the OpenAI embeddings endpoint in batches <= _OPENAI_BATCH_SIZE."""
        if not texts:
            return []

        client = self._get_client()
        vectors: list[np.ndarray] = []

        for start in range(0, len(texts), _OPENAI_BATCH_SIZE):
            batch = texts[start: start + _OPENAI_BATCH_SIZE]
            try:
                resp = client.embeddings.create(
                    model=self.model_name,
                    input=batch,
                )
            except OpenAIError as exc:
                raise RuntimeError(
                    f"OpenAI embeddings API error (model={self.model_name}): {exc}"
                ) from exc
            except Exception as exc:
                raise RuntimeError(
                    f"Unexpected error while calling OpenAI embeddings: {exc}"
                ) from exc

            # Preserve API-returned order via index, just in case.
            data_sorted = sorted(resp.data, key=lambda d: d.index)
            for item in data_sorted:
                raw = np.asarray(item.embedding, dtype=np.float32)
                vectors.append(self._l2_normalise(raw))

        return vectors

    def embed(self, texts: list[str]) -> list[np.ndarray]:
        """
        Embed a batch of texts. Returns L2-normalised float32 numpy arrays.
        Cache hits are resolved before calling the API.
        """
        if not texts:
            return []

        cached_results, miss_indices = self._cache.get_batch(texts, self.model_name)

        if miss_indices:
            miss_texts = [texts[i] for i in miss_indices]
            new_vecs = self._call_openai(miss_texts)

            # Persist misses into the cache for reuse across runs.
            self._cache.set_batch(miss_texts, self.model_name, list(new_vecs))

            for i, idx in enumerate(miss_indices):
                cached_results[idx] = new_vecs[i]

        return [r for r in cached_results]  # type: ignore[return-value]

    def embed_query(self, text: str) -> np.ndarray:
        """Embed a single query string."""
        return self.embed([text])[0]

    @property
    def vector_size(self) -> int:
        return DENSE_VECTOR_SIZE
