# RAG System — Architecture & Design Decisions

## Overview

This is a **Retrieval-Augmented Generation (RAG)** ingestion and retrieval system built on top of **Qdrant Cloud** (free tier). It is designed as a POC (Proof of Concept) that demonstrates production-quality patterns: structured chunking, caching, hybrid search, and clean CLI tooling.

---

## Directory Structure

```
Qdrant/
├── .env.example          ← Template for secrets (copy → .env)
├── requirements.txt      ← Python dependencies
├── data/
│   └── raw/              ← Drop source documents here
├── cache/
│   └── embeddings/       ← diskcache embedding store (auto-created)
├── src/
│   ├── config.py         ← All settings loaded from env vars
│   ├── loaders.py        ← File-type specific document loaders
│   ├── chunker.py        ← Structured-based chunking algorithm
│   ├── embeddings.py     ← Dense + Hybrid embedders with cache
│   ├── qdrant_manager.py ← Qdrant client wrapper (upsert, search, manage)
│   └── cache_manager.py  ← diskcache embedding cache
├── scripts/
│   ├── ingest.py         ← Ingestion pipeline CLI
│   ├── manage.py         ← Database management CLI
│   └── query.py          ← Query / retrieval CLI
└── docs/
    └── architecture.md   ← This file
```

---

## Component Design

### 1. Document Loaders (`src/loaders.py`)

| Format | Library | Notes |
|--------|---------|-------|
| `.txt`, `.md` | stdlib | Direct text read, UTF-8 |
| `.pdf` | `pymupdf` (fitz) | Page-by-page text extraction; preserves page numbers |
| `.docx` | `python-docx` | Paragraphs + tables; tables tagged `[TABLE]…[/TABLE]` |
| `.xlsx`, `.xls` | `pandas` + `openpyxl` | Per-sheet extraction; header row preserved |
| `.csv` | `pandas` | Column headers included as first row |
| `.html`, `.htm` | `beautifulsoup4` | Scripts/styles removed; clean body text |
| `.json` | stdlib | Pretty-printed JSON string |

Each loader returns `list[RawPage]`, a dataclass carrying `text` and `metadata` (source_file, file_type, page number, sheet name, etc.).

---

### 2. Structured-Based Chunking (`src/chunker.py`)

**Why structured chunking over fixed-size sliding windows?**

Fixed-size chunking (e.g., every 512 characters) is simple but semantically blind: it can split mid-sentence, separate a table header from its data rows, or merge unrelated sections. Structured chunking respects the document's own hierarchy.

**Algorithm (3 phases):**

#### Phase 1 — Parse into elements
The raw text is split into typed structural elements:
- `heading` (Markdown `#` syntax or setext underlines) → carries a depth level (1–6)
- `paragraph` → blocks separated by blank lines
- `table` → `[TABLE]…[/TABLE]` tagged blocks from the Word loader
- `code` → fenced code blocks (` ``` `)
- `list` → lines starting with `-`, `*`, or `•`

Code and table blocks are **never split** — they are always emitted as single chunks.

#### Phase 2 — Group under headings
Elements are accumulated into a running group under the current section heading. A breadcrumb is maintained (`"Introduction > Key Concepts"`). When adding the next element would exceed `CHUNK_SIZE`, the group is flushed as a chunk.

#### Phase 3 — Overlap context
The last `CHUNK_OVERLAP` characters of the previous chunk are prepended to the next chunk as a context prefix. This prevents the retriever from missing answers that straddle a chunk boundary.

**Metadata per chunk:**
```json
{
  "text":        "…chunk content…",
  "source_file": "report.pdf",
  "source_path": "/data/raw/report.pdf",
  "file_type":   "pdf",
  "chunk_index": 12,
  "section":     "Results > Quantitative Analysis",
  "page":        5,
  "char_count":  487,
  "ingested_at": "2025-04-15T14:32:00Z"
}
```

---

### 3. Embeddings (`src/embeddings.py`)

#### Dense Embedder (`DenseEmbedder`)

- **Model**: `all-MiniLM-L6-v2` (sentence-transformers)
  - English-optimised, 384-dimensional output
  - Fast inference (~14k sentences/sec on CPU)
  - Strong performance on semantic textual similarity benchmarks
- **Distance metric**: Cosine similarity
  - Vectors are L2-normalised before upload, so cosine = dot-product (faster Qdrant search)
- **Cache**: Every encoded text is stored in `diskcache` keyed by `SHA-256(text) + model_name`. On the next run, cache hits bypass the model entirely.

**Why `all-MiniLM-L6-v2` for English?**
It was trained specifically on English sentence pairs (MS-MARCO, NLI, etc.) and offers an excellent speed/quality tradeoff for POC use. Alternative: `BAAI/bge-small-en-v1.5` for better retrieval benchmarks at the same dimensionality.

#### Hybrid Embedder (`HybridEmbedder`)

Adds a **sparse vector** to every point alongside the dense vector.

**Sparse vector construction (hash-trick BM25-lite):**
1. Tokenise text (lowercase, remove stopwords, filter 2-char tokens)
2. Count term frequencies (TF)
3. Apply log-normalised TF: `weight = (1 + log(tf)) / doc_length`
4. Map each token to an integer index: `idx = hash(token) % VOCAB_SIZE`
5. Handle hash collisions by summing weights at the same index
6. L1-normalise the final weight vector

This produces a sparse `{index: value}` dict compatible with Qdrant's `SparseVector`.

**Why not corpus-wide BM25 (with IDF)?**
True BM25 requires knowing the full corpus to compute Inverse Document Frequency. That's incompatible with incremental ingestion (you'd need to re-embed everything when new documents are added). The per-document TF approximation works well for keyword recall without that constraint.

**Hybrid search scoring:**
Qdrant's built-in **Reciprocal Rank Fusion (RRF)** combines the ranked lists from dense and sparse searches without needing a manually tuned mixing weight.

---

### 4. Embedding Cache (`src/cache_manager.py`)

- Library: `diskcache` — persistent, file-based, pickle serialisation
- Key: `model_slug:sha256(text)`
- Default TTL: 24 hours (configurable via `CACHE_TTL`)
- Size limit: 2 GB
- Thread-safe (diskcache uses file locks)

**Impact**: On a typical re-ingestion run (e.g., adding 5 new files to a 200-file corpus), ~97% of embeddings are served from cache, reducing run time from minutes to seconds.

---

### 5. Qdrant Collection Schema

#### Dense collection
```
vectors_config:
  "dense": VectorParams(size=384, distance=COSINE)
```

#### Hybrid collection
```
vectors_config:
  "dense": VectorParams(size=384, distance=COSINE)
sparse_vectors_config:
  "sparse": SparseVectorParams()
```

Each point payload follows the schema described in the chunking section above.

---

## Scripts Reference

### `scripts/ingest.py`

```
python scripts/ingest.py [OPTIONS]

Options:
  --file TEXT          Ingest a single file
  --folder TEXT        Source folder (default: data/raw/)
  --mode [dense|hybrid]
  --chunk-size INT     Max chars per chunk (default: 512)
  --overlap INT        Overlap chars (default: 64)
  --dry-run            Parse/chunk only, no upload
  --force              Re-ingest already-indexed files
  --recreate           Delete and recreate collection first
```

### `scripts/manage.py`

```
python scripts/manage.py COMMAND [OPTIONS]

Commands:
  info        Collection metadata
  list        All collections in the instance
  stats       Per-file chunk counts and section breakdown
  scroll      Page through stored points
  delete      Delete a whole collection (--confirm required)
  delete-doc  Remove all chunks for a specific source file
  recreate    Drop and recreate empty collection
  export      Dump all payloads to JSON
  cache       Show/clear embedding cache stats
```

### `scripts/query.py`

```
python scripts/query.py QUERY_TEXT [OPTIONS]

Options:
  --mode [dense|hybrid]
  --top-k INT          Number of results (default: 5)
  --min-score FLOAT    Minimum similarity score threshold
  --filter KEY=VALUE   Payload filter (repeatable)
  --verbose            Show full chunk text
  --output FILE        Export results to JSON
  --collection TEXT    Override collection name
```

---

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `QDRANT_URL` | *(required)* | Qdrant Cloud cluster URL |
| `QDRANT_API_KEY` | *(required)* | API key for the cluster |
| `QDRANT_COLLECTION` | `rag_documents` | Dense collection name |
| `QDRANT_COLLECTION_HYBRID` | `rag_documents_hybrid` | Hybrid collection name |
| `DENSE_MODEL` | `all-MiniLM-L6-v2` | sentence-transformers model |
| `DENSE_VECTOR_SIZE` | `384` | Vector dimensions (must match model) |
| `CHUNK_SIZE` | `512` | Target chunk size in characters |
| `CHUNK_OVERLAP` | `64` | Overlap between consecutive chunks |
| `MIN_CHUNK_SIZE` | `80` | Chunks shorter than this are discarded |
| `ENABLE_CACHE` | `true` | Enable embedding disk cache |
| `CACHE_TTL` | `86400` | Cache entry TTL in seconds |
| `BATCH_SIZE` | `64` | Embedding batch size |
| `SPARSE_VOCAB_SIZE` | `30000` | Hash space for sparse vectors |

---

## Quick Start

```bash
# 1. Install dependencies
pip install -r requirements.txt

# 2. Configure environment
cp .env.example .env
# Edit .env: set QDRANT_URL and QDRANT_API_KEY

# 3. Download NLTK data (first run)
python -c "import nltk; nltk.download('punkt')"

# 4. Drop your documents into data/raw/

# 5. Ingest (dense mode)
python scripts/ingest.py

# 6. Query
python scripts/query.py "What are the main findings?"

# 7. Manage
python scripts/manage.py stats
python scripts/manage.py info
```

---

## Extending the System

- **New file type**: Add a loader function to `src/loaders.py` and register it in `SUPPORTED_EXTENSIONS` in `src/config.py`.
- **Different embedding model**: Change `DENSE_MODEL` and `DENSE_VECTOR_SIZE` in `.env`. Run `python scripts/manage.py recreate` to rebuild with the new dimensionality, then re-ingest.
- **Reranking**: Add a reranker step after retrieval in `scripts/query.py` (e.g., cross-encoder `ms-marco-MiniLM-L-6-v2`).
- **Multi-tenancy**: Use Qdrant payload filters (`--filter user_id=123`) to partition the collection by user without separate collections.
