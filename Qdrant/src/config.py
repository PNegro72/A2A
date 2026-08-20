"""
Central configuration — reads from environment variables (or .env file).
All other modules import from here; never hard-code paths or secrets elsewhere.
"""

from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

# Load .env from the project root (one level above src/)
_ROOT = Path(__file__).parent.parent
load_dotenv(_ROOT / ".env")

# ─────────────────────────────────────────────
#  Paths
# ─────────────────────────────────────────────
BASE_DIR: Path = _ROOT
DATA_DIR: Path = BASE_DIR / "data" / "raw"
CACHE_DIR: Path = BASE_DIR / "cache"

# Ensure cache dir exists at import time
CACHE_DIR.mkdir(parents=True, exist_ok=True)

# ─────────────────────────────────────────────
#  Qdrant Cloud
# ─────────────────────────────────────────────
QDRANT_URL: str = os.environ["QDRANT_URL"]
QDRANT_API_KEY: str = os.environ["QDRANT_API_KEY"]
# qdrant-client defaults to port 6333 when QDRANT_URL has no explicit port.
# Some networks (e.g. corporate firewalls) block outbound 6333 but allow 443,
# which Qdrant Cloud also serves the REST API on — hence this override.
QDRANT_PORT: int = int(os.getenv("QDRANT_PORT", "443"))

COLLECTION_NAME: str = os.getenv("QDRANT_COLLECTION", "CVs")
COLLECTION_NAME_HYBRID: str = os.getenv("QDRANT_COLLECTION_HYBRID", "rag_documents_hybrid")

# ─────────────────────────────────────────────
#  Embedding — Dense (OpenAI)
# ─────────────────────────────────────────────
# Default dense model is OpenAI's text-embedding-3-small (1536 dimensions).
# Multilingual by design — superior to sentence-transformers for Spanish/
# English mixed corpora. Uses cosine similarity (L2-normalised vectors).
OPENAI_API_KEY: str = os.environ["OPENAI_API_KEY"]
DENSE_MODEL: str = os.getenv("DENSE_MODEL", "text-embedding-3-small")
DENSE_VECTOR_SIZE: int = int(os.getenv("DENSE_VECTOR_SIZE", "1536"))

# Sparse (hybrid) hash vocabulary size — higher = fewer collisions
SPARSE_VOCAB_SIZE: int = int(os.getenv("SPARSE_VOCAB_SIZE", "30000"))

# ─────────────────────────────────────────────
#  Chunking
# ─────────────────────────────────────────────
# Larger chunks are safe with OpenAI embeddings (8k-token input limit) and
# give richer context to the LLM at answer-generation time.
CHUNK_SIZE: int = int(os.getenv("CHUNK_SIZE", "2500"))       # target tokens / chars
CHUNK_OVERLAP: int = int(os.getenv("CHUNK_OVERLAP", "400"))  # overlap between chunks
MIN_CHUNK_SIZE: int = int(os.getenv("MIN_CHUNK_SIZE", "100")) # discard smaller chunks
MIN_SCORE: float = float(os.getenv("MIN_SCORE", "0.35"))     # cosine similarity threshold

# ─────────────────────────────────────────────
#  Cache
# ─────────────────────────────────────────────
ENABLE_CACHE: bool = os.getenv("ENABLE_CACHE", "true").lower() == "true"
CACHE_TTL: int = int(os.getenv("CACHE_TTL", "86400"))  # seconds

# ─────────────────────────────────────────────
#  Ingestion
# ─────────────────────────────────────────────
# BATCH_SIZE is capped at 32 to stay well within OpenAI rate limits and
# avoid per-request token ceilings when chunks are large.
BATCH_SIZE: int = int(os.getenv("BATCH_SIZE", "32"))

# Supported file extensions → loader key
SUPPORTED_EXTENSIONS: dict[str, str] = {
    ".txt":  "text",
    ".md":   "markdown",
    ".pdf":  "pdf",
    ".docx": "word",
    ".doc":  "word",
    ".xlsx": "excel",
    ".xls":  "excel",
    ".csv":  "csv",
    ".html": "html",
    ".htm":  "html",
    ".json": "json",
    ".pptx": "pptx",
    ".ppt":  "pptx",
}
