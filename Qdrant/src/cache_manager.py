"""
Embedding cache — persistent, disk-backed, keyed by (text_hash, model_name).

Why cache embeddings?
  Embedding models are CPU/GPU-intensive.  For a RAG system that may re-ingest
  updated documents or serve repeated queries, caching saves significant time
  and avoids redundant model calls.  diskcache stores numpy arrays efficiently
  using pickle, survives process restarts, and supports TTL eviction.
"""

from __future__ import annotations

import hashlib
import pickle
from typing import Optional

import numpy as np

from src.config import CACHE_DIR, CACHE_TTL, ENABLE_CACHE


def _text_key(text: str, model_name: str) -> str:
    """Deterministic cache key = SHA-256(text) + model slug."""
    h = hashlib.sha256(text.encode("utf-8")).hexdigest()
    slug = model_name.replace("/", "_").replace("-", "_")
    return f"{slug}:{h}"


class EmbeddingCache:
    """
    Thread-safe disk cache for embedding vectors.

    Usage:
        cache = EmbeddingCache()
        vec = cache.get("hello world", "all-MiniLM-L6-v2")  # None on miss
        cache.set("hello world", "all-MiniLM-L6-v2", np.array([...]))
    """

    def __init__(self, enabled: bool = ENABLE_CACHE, ttl: int = CACHE_TTL) -> None:
        self._enabled = enabled
        self._ttl = ttl
        self._cache = None
        if enabled:
            self._cache = self._open_cache()

    def _open_cache(self):
        try:
            import diskcache
            return diskcache.Cache(str(CACHE_DIR / "embeddings"), size_limit=2 * 2**30)
        except ImportError:
            print("[cache] diskcache not installed — caching disabled.")
            return None

    def get(self, text: str, model_name: str) -> Optional[np.ndarray]:
        if self._cache is None:
            return None
        key = _text_key(text, model_name)
        raw = self._cache.get(key)
        if raw is None:
            return None
        return pickle.loads(raw)

    def set(self, text: str, model_name: str, vector: np.ndarray) -> None:
        if self._cache is None:
            return
        key = _text_key(text, model_name)
        self._cache.set(key, pickle.dumps(vector), expire=self._ttl)

    def get_batch(
        self, texts: list[str], model_name: str
    ) -> tuple[list[Optional[np.ndarray]], list[int]]:
        """
        Return (vectors_or_None, miss_indices).

        vectors_or_None[i] is None when text[i] was not cached.
        miss_indices lists the positions that need to be computed.
        """
        results: list[Optional[np.ndarray]] = []
        misses: list[int] = []
        for i, t in enumerate(texts):
            vec = self.get(t, model_name)
            results.append(vec)
            if vec is None:
                misses.append(i)
        return results, misses

    def set_batch(
        self, texts: list[str], model_name: str, vectors: list[np.ndarray]
    ) -> None:
        for text, vec in zip(texts, vectors):
            self.set(text, model_name, vec)

    def stats(self) -> dict:
        if self._cache is None:
            return {"enabled": False}
        return {
            "enabled":    True,
            "size_bytes": self._cache.volume(),
            "item_count": len(self._cache),
            "ttl_secs":   self._ttl,
        }

    def clear(self) -> None:
        if self._cache is not None:
            self._cache.clear()


# Module-level singleton — shared across all importers
_default_cache: Optional[EmbeddingCache] = None


def get_cache() -> EmbeddingCache:
    global _default_cache
    if _default_cache is None:
        _default_cache = EmbeddingCache()
    return _default_cache
