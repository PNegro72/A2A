"""
FastAPI REST API wrapping the RAG backend.

Endpoints
---------
GET  /health                    → connectivity check + list collections
GET  /collections               → list all collections in the cluster
POST /collections               → create a new (empty) collection
GET  /collection/info           → collection metadata
POST /ingest                    → upload & ingest files (multipart/form-data)
POST /ingest/base64             → upload & ingest files encoded as base64 JSON
POST /search                    → semantic search
DELETE /documents/{source_file} → delete all chunks from a file

Most endpoints accept an optional ``collection`` field; if omitted, the default
collection from config is used. Collection names must match ``[A-Za-z0-9_-]+``.

Run from the Qdrant/ directory:
    uvicorn api.main:app --reload --port 8000
"""

from __future__ import annotations

import base64
import hashlib
import re
import sys
import tempfile
from pathlib import Path
from typing import Optional

# Allow  uvicorn api.main:app  launched from Qdrant/
sys.path.insert(0, str(Path(__file__).parent.parent))

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from src.config import BATCH_SIZE, CHUNK_OVERLAP, CHUNK_SIZE, MIN_SCORE, SUPPORTED_EXTENSIONS
from src.chunker import chunk_pages
from src.openai_embedder import OpenAIEmbedder
from src.loaders import load_document
from src.qdrant_manager import QdrantManager
from src.validator import validate_file

app = FastAPI(title="RAGaaS API", version="2.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


# ── Pydantic schemas ────────────────────────────────────────────────────────

class CollectionStats(BaseModel):
    name: str
    points_count: Optional[int] = None
    vectors_count: Optional[int] = None
    status: Optional[str] = None


class HealthResponse(BaseModel):
    status: str
    collections: list[str]
    active_collection: Optional[CollectionStats] = None


class CollectionInfo(BaseModel):
    name: str
    status: str
    vectors_count: Optional[int] = None
    points_count: Optional[int] = None
    indexed_vectors_count: Optional[int] = None


class IngestFileResult(BaseModel):
    name: str
    status: str
    action: Optional[str] = None   # "created" | "updated" | "unchanged"
    chunks: int = 0
    pages: int = 0
    error: Optional[str] = None


class IngestResponse(BaseModel):
    results: list[IngestFileResult]
    total_chunks: int


class SearchRequest(BaseModel):
    query: str
    model_name: str = "text-embedding-3-small"
    top_k: int = 5
    mode: str = "dense"
    filter: Optional[dict] = None
    min_score: float = MIN_SCORE
    collection: Optional[str] = None


class SearchResult(BaseModel):
    score: float
    text: str
    source_file: str
    section: str
    page: int
    chunk_index: int
    char_count: int
    ingested_at: str
    embedding_model: str
    id: str


class SearchResponse(BaseModel):
    results: list[SearchResult]


class IndexedDocument(BaseModel):
    source_file: str
    chunk_count: int
    file_type: str
    ingested_at: str
    embedding_model: str


class DocumentsResponse(BaseModel):
    documents: list[IndexedDocument]
    total_documents: int
    total_chunks: int


class DeleteResponse(BaseModel):
    source_file: str
    deleted: int


class Base64File(BaseModel):
    filename: str
    content: str  # base64-encoded bytes


class IngestBase64Request(BaseModel):
    files: list[Base64File]
    model_name: str = "text-embedding-3-small"
    mode: str = "dense"
    collection: Optional[str] = None
    chunk_size: Optional[int] = None
    chunk_overlap: Optional[int] = None


class CollectionsResponse(BaseModel):
    collections: list[str]


class CreateCollectionRequest(BaseModel):
    name: str
    mode: str = "dense"


class CreateCollectionResponse(BaseModel):
    name: str
    created: bool
    message: str


# ── Helpers ─────────────────────────────────────────────────────────────────

def _compute_file_hash(path: Path) -> str:
    """Return the SHA-256 hex digest of a file, read in 64 KB blocks."""
    sha256 = hashlib.sha256()
    with open(path, "rb") as f:
        for block in iter(lambda: f.read(65536), b""):
            sha256.update(block)
    return sha256.hexdigest()


_COLLECTION_NAME_RE = re.compile(r"^[A-Za-z0-9_-]{1,64}$")


def _validate_collection_name(name: str) -> str:
    """Normalise + validate a user-supplied Qdrant collection name."""
    cleaned = (name or "").strip()
    if not _COLLECTION_NAME_RE.match(cleaned):
        raise HTTPException(
            status_code=400,
            detail=(
                "Nombre de colección inválido. Usá solo letras, números, '_' o '-' "
                "(1 a 64 caracteres)."
            ),
        )
    return cleaned


# ── Endpoints ───────────────────────────────────────────────────────────────

@app.get("/health", response_model=HealthResponse)
def health(collection: Optional[str] = None):
    """Returns API status, list of collections, and stats of the active collection.

    If ``collection`` is provided, the active_collection stats refer to it;
    otherwise the default (config-defined) collection is reported.
    """
    try:
        manager = QdrantManager(
            mode="dense",
            collection=_validate_collection_name(collection) if collection else None,
        )
        collections = manager.list_collections()
        active_collection = None
        if manager.collection_exists():
            info = manager.get_info()
            active_collection = CollectionStats(
                name=info["name"],
                points_count=info.get("points_count"),
                vectors_count=info.get("vectors_count"),
                status=info.get("status"),
            )
        return HealthResponse(status="ok", collections=collections, active_collection=active_collection)
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=503, detail=str(exc))


@app.get("/collections", response_model=CollectionsResponse)
def list_collections():
    """Return all collection names available in the Qdrant cluster."""
    try:
        manager = QdrantManager(mode="dense")
        return CollectionsResponse(collections=manager.list_collections())
    except Exception as exc:
        raise HTTPException(status_code=503, detail=str(exc))


@app.post("/collections", response_model=CreateCollectionResponse)
def create_collection_endpoint(req: CreateCollectionRequest):
    """Create a new (empty) collection with the requested name.

    If the collection already exists, returns ``created=False`` (no-op).
    """
    if req.mode not in ("dense", "hybrid"):
        raise HTTPException(status_code=400, detail="mode debe ser 'dense' o 'hybrid'.")
    name = _validate_collection_name(req.name)

    try:
        manager = QdrantManager(mode=req.mode, collection=name)
        if manager.collection_exists():
            return CreateCollectionResponse(
                name=name,
                created=False,
                message=f"La colección '{name}' ya existe.",
            )
        manager.create_collection()
        return CreateCollectionResponse(
            name=name,
            created=True,
            message=f"Colección '{name}' creada correctamente.",
        )
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@app.get("/collection/info", response_model=CollectionInfo)
def collection_info(mode: str = "dense", collection: Optional[str] = None):
    """Returns metadata for a collection (points count, status, etc.)."""
    try:
        manager = QdrantManager(
            mode=mode,
            collection=_validate_collection_name(collection) if collection else None,
        )
        if not manager.collection_exists():
            raise HTTPException(
                status_code=404,
                detail=f"Collection '{manager.collection}' does not exist.",
            )
        info = manager.get_info()
        return CollectionInfo(**info)
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@app.post("/ingest", response_model=IngestResponse)
async def ingest(
    files: list[UploadFile] = File(...),
    model_name: str = Form("text-embedding-3-small"),
    mode: str = Form("dense"),
    collection: Optional[str] = Form(None),
):
    """
    Upload one or more files, run the full ingestion pipeline
    (load → chunk → embed → upsert), and return per-file stats.

    The entire request is rejected (HTTP 400) if:
    - No files are provided.
    - Any file has an unsupported extension.
    - Any file fails structural validation (empty, too large, corrupted, wrong format).
    """
    if not files:
        raise HTTPException(status_code=400, detail="Debes enviar al menos un archivo.")

    with tempfile.TemporaryDirectory() as tmpdir:
        # ── Phase 1: save + validate ALL files before processing any ──────────
        saved: list[tuple[str, str, Path]] = []  # (filename, loader_key, tmp_path)
        validation_errors: list[str] = []

        for upload in files:
            filename = upload.filename or "unknown"
            suffix = Path(filename).suffix.lower()
            loader_key = SUPPORTED_EXTENSIONS.get(suffix)

            if not loader_key:
                validation_errors.append(
                    f"'{filename}': formato '{suffix}' no está permitido. "
                    f"Formatos aceptados: {', '.join(SUPPORTED_EXTENSIONS.keys())}."
                )
                continue

            tmp_path = Path(tmpdir) / filename
            tmp_path.write_bytes(await upload.read())

            try:
                validate_file(tmp_path)
            except ValueError as exc:
                validation_errors.append(str(exc))
                continue

            saved.append((filename, loader_key, tmp_path))

        if validation_errors:
            raise HTTPException(
                status_code=400,
                detail={"message": "La carga fue rechazada por errores de validación.", "errors": validation_errors},
            )

        # ── Phase 2: process all validated files ──────────────────────────────
        manager = QdrantManager(
            mode=mode,
            collection=_validate_collection_name(collection) if collection else None,
        )
        manager.create_collection()
        embedder = OpenAIEmbedder(model_name=model_name)

        results: list[IngestFileResult] = []
        total_chunks = 0

        for filename, loader_key, tmp_path in saved:
            try:
                new_hash = _compute_file_hash(tmp_path)
                existing_hash = manager.get_file_hash(filename)

                if existing_hash == new_hash:
                    results.append(IngestFileResult(
                        name=filename,
                        status="unchanged",
                        action="unchanged",
                    ))
                    continue

                # Cross-name duplicate: same content already indexed under a different filename
                if existing_hash is None:
                    duplicate_source = manager.get_source_by_hash(new_hash)
                    if duplicate_source and duplicate_source != filename:
                        results.append(IngestFileResult(
                            name=filename,
                            status="duplicate",
                            action="duplicate",
                            error=duplicate_source,
                        ))
                        continue

                action = "updated" if existing_hash is not None else "created"
                manager.delete_by_source(filename)

                pages = load_document(tmp_path, loader_key)
                chunks = chunk_pages(pages, chunk_size=CHUNK_SIZE, overlap=CHUNK_OVERLAP)

                if not chunks:
                    results.append(IngestFileResult(name=filename, status="skipped (no chunks)"))
                    continue

                for chunk in chunks:
                    chunk.metadata["embedding_model"] = model_name
                    chunk.metadata["file_hash"] = new_hash

                all_embeddings: list = []
                texts = [c.text for c in chunks]
                for start in range(0, len(texts), BATCH_SIZE):
                    batch = texts[start: start + BATCH_SIZE]
                    all_embeddings.extend(embedder.embed(batch))

                uploaded = manager.upsert_chunks(chunks, all_embeddings)
                total_chunks += uploaded
                results.append(IngestFileResult(
                    name=filename,
                    status="ok",
                    action=action,
                    chunks=len(chunks),
                    pages=len(pages),
                ))
            except Exception as exc:
                results.append(IngestFileResult(
                    name=filename,
                    status="error",
                    error=str(exc),
                ))

    return IngestResponse(results=results, total_chunks=total_chunks)


@app.post("/ingest/base64", response_model=IngestResponse)
async def ingest_base64(req: IngestBase64Request):
    """
    Ingest files sent as base64-encoded strings inside a JSON body.

    Each item in ``files`` must have:
    - ``filename``: original file name including extension (e.g. ``"report.pdf"``)
    - ``content``:  base64-encoded file bytes (standard or URL-safe alphabet)

    Example body::

        {
          "files": [
            {
              "filename": "report.pdf",
              "content": "<base64 string>"
            }
          ],
          "model_name": "text-embedding-3-small",
          "mode": "dense"
        }
    """
    if not req.files:
        raise HTTPException(status_code=400, detail="Debes enviar al menos un archivo.")

    with tempfile.TemporaryDirectory() as tmpdir:
        # ── Phase 1: decode base64 + validate ALL files before processing any ─
        saved: list[tuple[str, str, Path]] = []  # (filename, loader_key, tmp_path)
        validation_errors: list[str] = []

        for f in req.files:
            filename = f.filename.strip() if f.filename else ""
            if not filename:
                validation_errors.append("Se recibió un archivo sin nombre.")
                continue

            if not f.content:
                validation_errors.append(f"'{filename}': el contenido base64 está vacío.")
                continue

            suffix = Path(filename).suffix.lower()
            loader_key = SUPPORTED_EXTENSIONS.get(suffix)

            if not loader_key:
                validation_errors.append(
                    f"'{filename}': formato '{suffix}' no está permitido. "
                    f"Formatos aceptados: {', '.join(SUPPORTED_EXTENSIONS.keys())}."
                )
                continue

            try:
                raw_bytes = base64.b64decode(f.content)
            except Exception:
                validation_errors.append(
                    f"'{filename}': el contenido base64 es inválido o está malformado."
                )
                continue

            tmp_path = Path(tmpdir) / filename
            tmp_path.write_bytes(raw_bytes)

            try:
                validate_file(tmp_path)
            except ValueError as exc:
                validation_errors.append(str(exc))
                continue

            saved.append((filename, loader_key, tmp_path))

        if validation_errors:
            raise HTTPException(
                status_code=400,
                detail={"message": "La carga fue rechazada por errores de validación.", "errors": validation_errors},
            )

        # ── Phase 2: process all validated files ──────────────────────────────
        effective_chunk_size = req.chunk_size if req.chunk_size is not None else CHUNK_SIZE
        effective_overlap = req.chunk_overlap if req.chunk_overlap is not None else CHUNK_OVERLAP

        if not 200 <= effective_chunk_size <= 10000:
            raise HTTPException(status_code=400, detail="chunk_size debe estar entre 200 y 10000.")
        if not 0 <= effective_overlap < effective_chunk_size:
            raise HTTPException(
                status_code=400,
                detail="chunk_overlap debe ser ≥ 0 y menor que chunk_size.",
            )

        manager = QdrantManager(
            mode=req.mode,
            collection=_validate_collection_name(req.collection) if req.collection else None,
        )
        manager.create_collection()
        embedder = OpenAIEmbedder(model_name=req.model_name)

        results: list[IngestFileResult] = []
        total_chunks = 0

        for filename, loader_key, tmp_path in saved:
            try:
                new_hash = _compute_file_hash(tmp_path)
                existing_hash = manager.get_file_hash(filename)

                if existing_hash == new_hash:
                    results.append(IngestFileResult(
                        name=filename,
                        status="unchanged",
                        action="unchanged",
                    ))
                    continue

                # Cross-name duplicate: same content already indexed under a different filename
                if existing_hash is None:
                    duplicate_source = manager.get_source_by_hash(new_hash)
                    if duplicate_source and duplicate_source != filename:
                        results.append(IngestFileResult(
                            name=filename,
                            status="duplicate",
                            action="duplicate",
                            error=duplicate_source,
                        ))
                        continue

                action = "updated" if existing_hash is not None else "created"
                manager.delete_by_source(filename)

                pages = load_document(tmp_path, loader_key)
                chunks = chunk_pages(
                    pages,
                    chunk_size=effective_chunk_size,
                    overlap=effective_overlap,
                )

                if not chunks:
                    results.append(IngestFileResult(name=filename, status="skipped (no chunks)"))
                    continue

                for chunk in chunks:
                    chunk.metadata["embedding_model"] = req.model_name
                    chunk.metadata["file_hash"] = new_hash
                    chunk.metadata["chunk_size_setting"] = effective_chunk_size
                    chunk.metadata["chunk_overlap_setting"] = effective_overlap

                all_embeddings: list = []
                texts = [c.text for c in chunks]
                for start in range(0, len(texts), BATCH_SIZE):
                    batch = texts[start: start + BATCH_SIZE]
                    all_embeddings.extend(embedder.embed(batch))

                uploaded = manager.upsert_chunks(chunks, all_embeddings)
                total_chunks += uploaded
                results.append(IngestFileResult(
                    name=filename,
                    status="ok",
                    action=action,
                    chunks=len(chunks),
                    pages=len(pages),
                ))
            except Exception as exc:
                results.append(IngestFileResult(
                    name=filename,
                    status="error",
                    error=str(exc),
                ))

    return IngestResponse(results=results, total_chunks=total_chunks)


@app.post("/search", response_model=SearchResponse)
def search(req: SearchRequest):
    """
    Embed the query and run a dense similarity search.
    Returns top-k results sorted by score descending.
    """
    if not req.query.strip():
        raise HTTPException(status_code=400, detail="La consulta no puede estar vacía.")
    if not 1 <= req.top_k <= 50:
        raise HTTPException(status_code=400, detail="top_k debe estar entre 1 y 50.")
    if req.mode not in ("dense", "hybrid"):
        raise HTTPException(status_code=400, detail="mode debe ser 'dense' o 'hybrid'.")

    try:
        manager = QdrantManager(
            mode=req.mode,
            collection=_validate_collection_name(req.collection) if req.collection else None,
        )
        if not manager.collection_exists():
            raise HTTPException(
                status_code=404,
                detail=(
                    f"No hay documentos indexados en la colección '{manager.collection}'. "
                    "Cargá documentos primero desde la pestaña 'Cargar archivos'."
                ),
            )
        embedder = OpenAIEmbedder(model_name=req.model_name)
        query_vec = embedder.embed_query(req.query)
        raw = manager.search_dense(
            query_vector=query_vec,
            top_k=req.top_k,
            filter_payload=req.filter,
        )
        filtered = [r for r in raw if r["score"] >= req.min_score]
        return SearchResponse(results=[SearchResult(**r) for r in filtered])
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@app.get("/documents", response_model=DocumentsResponse)
def list_documents(collection: Optional[str] = None):
    """
    Return the list of unique documents currently indexed in the collection,
    along with chunk count, file type, and ingestion timestamp per document.
    """
    try:
        manager = QdrantManager(
            mode="dense",
            collection=_validate_collection_name(collection) if collection else None,
        )
        if not manager.collection_exists():
            return DocumentsResponse(documents=[], total_documents=0, total_chunks=0)

        # Page through all points and aggregate by source_file
        aggregated: dict[str, dict] = {}
        offset = None
        while True:
            records, offset = manager.scroll(limit=256, offset=offset)
            for r in records:
                payload = r.get("payload", {})
                sf = payload.get("source_file")
                if not sf:
                    continue
                if sf not in aggregated:
                    aggregated[sf] = {
                        "source_file":     sf,
                        "chunk_count":     0,
                        "file_type":       payload.get("file_type", ""),
                        "ingested_at":     payload.get("ingested_at", ""),
                        "embedding_model": payload.get("embedding_model", ""),
                    }
                aggregated[sf]["chunk_count"] += 1
            if offset is None:
                break

        documents = [IndexedDocument(**v) for v in aggregated.values()]
        documents.sort(key=lambda d: d.ingested_at, reverse=True)
        return DocumentsResponse(
            documents=documents,
            total_documents=len(documents),
            total_chunks=sum(d.chunk_count for d in documents),
        )
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@app.delete("/documents/{source_file}", response_model=DeleteResponse)
def delete_document(source_file: str, collection: Optional[str] = None):
    """Delete all vector points whose payload.source_file matches the given name."""
    try:
        manager = QdrantManager(
            mode="dense",
            collection=_validate_collection_name(collection) if collection else None,
        )
        deleted = manager.delete_by_source(source_file)
        return DeleteResponse(source_file=source_file, deleted=deleted)
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))
