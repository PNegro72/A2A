"""
Qdrant wrapper — all database operations go through this class.

Supports two collection modes:
  dense   → single named vector "dense" (cosine), standard search
  hybrid  → named vectors "dense" (cosine) + sparse "sparse", hybrid RRF search

Collection payload schema (stored alongside every point):
  text          (str)   chunk text
  source_file   (str)   original filename
  source_path   (str)   absolute/relative path
  file_type     (str)   extension without dot
  chunk_index   (int)   global sequential index within the document
  section       (str)   heading breadcrumb, e.g. "Introduction > Key Concepts"
  page          (int)   page number (1-based; 1 for single-page formats)
  char_count    (int)   length of chunk text in characters
  ingested_at   (str)   ISO-8601 UTC timestamp of ingestion
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any, Optional

import numpy as np

from src.config import (
    COLLECTION_NAME,
    COLLECTION_NAME_HYBRID,
    DENSE_VECTOR_SIZE,
    QDRANT_API_KEY,
    QDRANT_URL,
)


# ─────────────────────────────────────────────
#  Qdrant imports (lazy to allow import without connection)
# ─────────────────────────────────────────────

def _qdrant_imports():
    from qdrant_client import QdrantClient
    from qdrant_client.models import (
        Distance,
        FieldCondition,
        Filter,
        MatchValue,
        PointStruct,
        SparseVector,
        SparseVectorParams,
        VectorParams,
        models,
    )
    return (
        QdrantClient, Distance, FieldCondition, Filter, MatchValue,
        PointStruct, SparseVector, SparseVectorParams, VectorParams, models,
    )


# ─────────────────────────────────────────────
#  Manager class
# ─────────────────────────────────────────────

class QdrantManager:
    """
    High-level interface to a single Qdrant collection.

    Parameters
    ----------
    mode          : "dense" or "hybrid"
    collection    : override the default collection name from config
    """

    def __init__(
        self,
        mode: str = "dense",
        collection: Optional[str] = None,
    ) -> None:
        if mode not in ("dense", "hybrid"):
            raise ValueError(f"mode must be 'dense' or 'hybrid', got {mode!r}")

        self.mode = mode
        self.collection = collection or (
            COLLECTION_NAME if mode == "dense" else COLLECTION_NAME_HYBRID
        )

        (
            QdrantClient, self._Distance, self._FieldCondition, self._Filter,
            self._MatchValue, self._PointStruct, self._SparseVector,
            self._SparseVectorParams, self._VectorParams, self._models,
        ) = _qdrant_imports()

        self._client = QdrantClient(url=QDRANT_URL, api_key=QDRANT_API_KEY, timeout=120)

    # ── Collection management ─────────────────

    def collection_exists(self) -> bool:
        try:
            self._client.get_collection(self.collection)
            return True
        except Exception:
            return False

    def create_collection(self, recreate: bool = False) -> None:
        """
        Create (or optionally recreate) the collection with the correct schema.

        Dense mode  → one named vector "dense", cosine distance.
        Hybrid mode → named vector "dense" + sparse vector "sparse".
        """
        if recreate and self.collection_exists():
            self._client.delete_collection(self.collection)
            print(f"[qdrant] Deleted existing collection '{self.collection}'")

        if self.collection_exists():
            print(f"[qdrant] Collection '{self.collection}' already exists — skipping creation.")
            self._ensure_payload_indexes()
            return

        vectors_config = {
            "dense": self._VectorParams(
                size=DENSE_VECTOR_SIZE,
                distance=self._Distance.COSINE,
            )
        }

        sparse_vectors_config = None
        if self.mode == "hybrid":
            sparse_vectors_config = {
                "sparse": self._SparseVectorParams()
            }

        self._client.create_collection(
            collection_name=self.collection,
            vectors_config=vectors_config,
            sparse_vectors_config=sparse_vectors_config,
        )
        print(f"[qdrant] Created collection '{self.collection}' (mode={self.mode})")
        self._ensure_payload_indexes()

    def _ensure_payload_indexes(self) -> None:
        """Create keyword indexes required for payload filtering and deletion."""
        for field in ("source_file", "file_type", "embedding_model", "file_hash"):
            try:
                self._client.create_payload_index(
                    collection_name=self.collection,
                    field_name=field,
                    field_schema="keyword",
                )
            except Exception:
                pass  # index already exists

    def delete_collection(self) -> bool:
        if not self.collection_exists():
            return False
        self._client.delete_collection(self.collection)
        return True

    def get_info(self) -> dict:
        info = self._client.get_collection(self.collection)
        return {
            "name":          self.collection,
            "status":        str(getattr(info, "status", "unknown")),
            "vectors_count": getattr(info, "vectors_count", None),
            "points_count":  getattr(info, "points_count", None),
            "indexed_vectors_count": getattr(info, "indexed_vectors_count", None),
        }

    def list_collections(self) -> list[str]:
        return [c.name for c in self._client.get_collections().collections]

    # ── Upsert ───────────────────────────────

    def upsert_chunks(
        self,
        chunks,                # list[Chunk] from chunker
        embeddings: list[Any], # list[np.ndarray] (dense) or list[dict] (hybrid)
    ) -> int:
        """
        Build PointStruct objects and upsert them in a single batch.
        Returns the number of points upserted.
        """
        now = datetime.now(timezone.utc).isoformat()
        points = []

        for chunk, emb in zip(chunks, embeddings):
            point_id = str(uuid.uuid4())
            payload = {
                "text":        chunk.text,
                "ingested_at": now,
                **chunk.metadata,
            }

            if self.mode == "dense":
                vec = emb.tolist() if isinstance(emb, np.ndarray) else emb
                vectors = {"dense": vec}
            else:  # hybrid
                vectors = {
                    "dense": emb["dense"].tolist(),
                    "sparse": self._SparseVector(
                        indices=emb["sparse_indices"],
                        values=emb["sparse_values"],
                    ),
                }

            points.append(
                self._PointStruct(id=point_id, vector=vectors, payload=payload)
            )

        self._client.upsert(collection_name=self.collection, points=points)
        return len(points)

    # ── Search ───────────────────────────────

    def search_dense(
        self,
        query_vector: np.ndarray,
        top_k: int = 5,
        filter_payload: Optional[dict] = None,
    ) -> list[dict]:
        """
        Cosine similarity search using the dense vector.
        Returns list of {score, text, metadata} dicts sorted by score DESC.
        """
        qdrant_filter = self._build_filter(filter_payload)
        results = self._client.query_points(
            collection_name=self.collection,
            query=query_vector.tolist(),
            using="dense",
            limit=top_k,
            query_filter=qdrant_filter,
            with_payload=True,
        )
        return [self._format_result(r) for r in results.points]

    def search_hybrid(
        self,
        query_dense: np.ndarray,
        query_sparse_indices: list[int],
        query_sparse_values: list[float],
        top_k: int = 5,
        filter_payload: Optional[dict] = None,
    ) -> list[dict]:
        """
        Hybrid search: dense + sparse via Qdrant's built-in RRF (Reciprocal Rank Fusion).
        Requires the collection to have been created in 'hybrid' mode.
        """
        from qdrant_client.models import Prefetch, Query, FusionQuery, Fusion

        qdrant_filter = self._build_filter(filter_payload)

        results = self._client.query_points(
            collection_name=self.collection,
            prefetch=[
                Prefetch(
                    query=query_dense.tolist(),
                    using="dense",
                    limit=top_k * 3,
                    filter=qdrant_filter,
                ),
                Prefetch(
                    query=self._SparseVector(
                        indices=query_sparse_indices,
                        values=query_sparse_values,
                    ),
                    using="sparse",
                    limit=top_k * 3,
                    filter=qdrant_filter,
                ),
            ],
            query=FusionQuery(fusion=Fusion.RRF),
            limit=top_k,
            with_payload=True,
        )
        return [self._format_result(r) for r in results.points]

    # ── Hash lookup ──────────────────────────

    def get_file_hash(self, source_file: str) -> Optional[str]:
        """Return the SHA-256 hash stored in the first chunk of a file, or None if not found."""
        if not self.collection_exists():
            return None
        try:
            results, _ = self._client.scroll(
                collection_name=self.collection,
                scroll_filter=self._Filter(
                    must=[self._FieldCondition(
                        key="source_file",
                        match=self._MatchValue(value=source_file),
                    )]
                ),
                limit=1,
                with_payload=True,
                with_vectors=False,
            )
            if not results:
                return None
            return (results[0].payload or {}).get("file_hash")
        except Exception:
            return None

    def get_source_by_hash(self, file_hash: str) -> Optional[str]:
        """Return the source_file of any existing document whose hash matches, or None."""
        if not self.collection_exists():
            return None
        try:
            results, _ = self._client.scroll(
                collection_name=self.collection,
                scroll_filter=self._Filter(
                    must=[self._FieldCondition(
                        key="file_hash",
                        match=self._MatchValue(value=file_hash),
                    )]
                ),
                limit=1,
                with_payload=True,
                with_vectors=False,
            )
            if not results:
                return None
            return (results[0].payload or {}).get("source_file")
        except Exception:
            return None

    # ── Delete by filter ─────────────────────

    def delete_by_source(self, source_file: str) -> int:
        """Delete all points whose payload.source_file matches the given filename."""
        from qdrant_client.models import Filter, FieldCondition, MatchValue

        result = self._client.delete(
            collection_name=self.collection,
            points_selector=self._models.FilterSelector(
                filter=Filter(
                    must=[FieldCondition(
                        key="source_file",
                        match=MatchValue(value=source_file),
                    )]
                )
            ),
        )
        return getattr(result, "deleted_count", 0) or 0

    # ── Scroll (list points) ─────────────────

    def scroll(
        self,
        limit: int = 10,
        offset: Optional[str] = None,
        with_vectors: bool = False,
    ) -> tuple[list[dict], Optional[str]]:
        """
        Page through all points in the collection.
        Returns (records, next_page_offset).
        """
        results, next_offset = self._client.scroll(
            collection_name=self.collection,
            limit=limit,
            offset=offset,
            with_payload=True,
            with_vectors=with_vectors,
        )
        records = [
            {
                "id":      r.id,
                "payload": r.payload,
            }
            for r in results
        ]
        return records, next_offset

    # ── Helpers ──────────────────────────────

    def _build_filter(self, filter_payload: Optional[dict]):
        if not filter_payload:
            return None
        conditions = [
            self._FieldCondition(key=k, match=self._MatchValue(value=v))
            for k, v in filter_payload.items()
        ]
        return self._Filter(must=conditions)

    @staticmethod
    def _format_result(r) -> dict:
        payload = r.payload or {}
        return {
            "score":           round(r.score, 6),
            "text":            payload.get("text", ""),
            "source_file":     payload.get("source_file", ""),
            "section":         payload.get("section", ""),
            "page":            payload.get("page", 1),
            "chunk_index":     payload.get("chunk_index", 0),
            "char_count":      payload.get("char_count", 0),
            "ingested_at":     payload.get("ingested_at", ""),
            "embedding_model": payload.get("embedding_model", ""),
            "id":              r.id,
        }
