"""
Embedding strategies.

Two classes are provided:

DenseEmbedder  (default / recommended for this POC)
  ─ Uses sentence-transformers to produce fixed-size dense vectors.
  ─ Distance metric: COSINE (vectors are L2-normalised before upload).
  ─ Default model: all-MiniLM-L6-v2  → 384-dimensional, English-optimised,
    fast inference.  Other good choices: BAAI/bge-small-en-v1.5 (same size,
    better retrieval benchmarks), all-mpnet-base-v2 (768d, higher quality).
  ─ Integrates with EmbeddingCache to avoid recomputing known vectors.

HybridEmbedder  (ready for when richer recall is needed)
  ─ Produces BOTH a dense vector (same as above) AND a sparse vector.
  ─ The sparse vector is a BM25-inspired TF representation using the hash trick:
      • tokenise, remove stopwords, compute term frequency per document
      • map each token to an integer index via hash(token) % VOCAB_SIZE
      • values are log(1 + tf) normalised by document length
    This approach works for INCREMENTAL ingestion (no corpus-wide IDF needed),
    avoids an external sparse-model dependency, and integrates natively with
    Qdrant's SparseVector type for efficient dot-product search.
  ─ Hybrid scoring = RRF (Reciprocal Rank Fusion) of dense + sparse results,
    performed inside Qdrant via its built-in query planner.
"""

from __future__ import annotations

import re
from collections import Counter
from typing import Optional

import numpy as np

from src.cache_manager import get_cache
from src.config import DENSE_MODEL, DENSE_VECTOR_SIZE, SPARSE_VOCAB_SIZE


# ─────────────────────────────────────────────
#  Shared helpers
# ─────────────────────────────────────────────

_STOPWORDS = frozenset(
    "a an the is it in on at to for of and or but not with as by "
    "from that this was are be been being have has had do does did "
    "will would could should may might shall can about".split()
)

_TOKEN_RE = re.compile(r"\b[a-z]{2,}\b")


def _tokenise(text: str) -> list[str]:
    tokens = _TOKEN_RE.findall(text.lower())
    return [t for t in tokens if t not in _STOPWORDS]


def _sparse_vector(text: str, vocab_size: int = SPARSE_VOCAB_SIZE) -> dict[int, float]:
    """
    Hash-trick BM25-lite sparse vector.

    Returns {index: weight} where weights are log-normalised TF values.
    Collisions are handled by summing weights at the same index.
    """
    tokens = _tokenise(text)
    if not tokens:
        return {}

    tf = Counter(tokens)
    total = len(tokens)
    result: dict[int, float] = {}

    for token, count in tf.items():
        idx = abs(hash(token)) % vocab_size
        # log-normalised TF  (prevents very frequent terms from dominating)
        weight = (1 + np.log(count)) / total
        result[idx] = result.get(idx, 0.0) + weight

    # L1-normalise so scores are comparable across documents of different lengths
    norm = sum(result.values())
    if norm > 0:
        result = {k: v / norm for k, v in result.items()}

    return result


def _to_qdrant_sparse(sparse: dict[int, float]):
    """Convert {index: value} dict to qdrant SparseVector namedtuple fields."""
    indices = list(sparse.keys())
    values  = [sparse[i] for i in indices]
    return indices, values


# ─────────────────────────────────────────────
#  Dense Embedder
# ─────────────────────────────────────────────

class DenseEmbedder:
    """
    Sentence-transformers dense embedder with disk cache.

    Parameters
    ----------
    model_name : sentence-transformers model id (HuggingFace hub or local path)
    cache      : EmbeddingCache instance (uses global default if None)
    """

    def __init__(
        self,
        model_name: str = DENSE_MODEL,
        cache=None,
    ) -> None:
        self.model_name = model_name
        self._cache = cache or get_cache()
        self._model = None  # lazy-load to avoid slow startup

    def _load_model(self):
        if self._model is None:
            try:
                from sentence_transformers import SentenceTransformer
            except ImportError as e:
                raise ImportError(
                    "sentence-transformers is required: pip install sentence-transformers"
                ) from e
            self._model = SentenceTransformer(self.model_name)
        return self._model

    def embed(self, texts: list[str]) -> list[np.ndarray]:
        """
        Embed a batch of texts.  Returns L2-normalised float32 numpy arrays.
        Cache hits are resolved before calling the model.
        """
        cached_results, miss_indices = self._cache.get_batch(texts, self.model_name)

        if miss_indices:
            model = self._load_model()
            miss_texts = [texts[i] for i in miss_indices]
            new_vecs = model.encode(
                miss_texts,
                normalize_embeddings=True,   # cosine ≡ dot-product after L2-norm
                show_progress_bar=False,
                convert_to_numpy=True,
            )
            # Store misses in cache
            self._cache.set_batch(miss_texts, self.model_name, list(new_vecs))
            # Merge back
            for i, idx in enumerate(miss_indices):
                cached_results[idx] = new_vecs[i]

        return [r for r in cached_results]  # type: ignore[return-value]

    def embed_query(self, text: str) -> np.ndarray:
        """Embed a single query string."""
        return self.embed([text])[0]

    @property
    def vector_size(self) -> int:
        return DENSE_VECTOR_SIZE


# ─────────────────────────────────────────────
#  Hybrid Embedder
# ─────────────────────────────────────────────

class HybridEmbedder:
    """
    Hybrid embedder that produces both dense and sparse vectors per text.

    Usage
    -----
    embedder = HybridEmbedder()
    results = embedder.embed(["text one", "text two"])
    # results[i] = {"dense": np.ndarray, "sparse_indices": list, "sparse_values": list}

    Why hybrid?
      Dense vectors capture semantic similarity well but struggle with exact
      keyword matches (e.g. product codes, names, technical terms).  Sparse
      vectors (BM25-style) excel at keyword matching.  Combining both via RRF
      in Qdrant gives the best of both worlds.
    """

    def __init__(
        self,
        model_name: str = DENSE_MODEL,
        vocab_size: int = SPARSE_VOCAB_SIZE,
        cache=None,
    ) -> None:
        # NOTA (2026-08-05): el componente denso usa OpenAIEmbedder (activo),
        # no el DenseEmbedder de sentence-transformers (legacy) de este mismo
        # módulo — mismo motivo que api/main.py. Import diferido para evitar
        # un ciclo de imports entre embeddings.py y openai_embedder.py.
        from src.openai_embedder import OpenAIEmbedder

        self._dense = OpenAIEmbedder(model_name=model_name, cache=cache)
        self._vocab_size = vocab_size

    def embed(self, texts: list[str]) -> list[dict]:
        """
        Returns a list of dicts, one per text:
          {
            "dense":          np.ndarray (float32, L2-normalised),
            "sparse_indices": list[int],
            "sparse_values":  list[float],
          }
        """
        dense_vecs = self._dense.embed(texts)
        results = []
        for text, dvec in zip(texts, dense_vecs):
            sparse = _sparse_vector(text, self._vocab_size)
            indices, values = _to_qdrant_sparse(sparse)
            results.append({
                "dense":          dvec,
                "sparse_indices": indices,
                "sparse_values":  values,
            })
        return results

    def embed_query(self, text: str) -> dict:
        return self.embed([text])[0]

    @property
    def vector_size(self) -> int:
        return self._dense.vector_size
