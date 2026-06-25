# RAGaaS — Backend RAG

Servicio FastAPI que maneja la ingesta de documentos, generación de embeddings y búsqueda vectorial. Corre en el **puerto 8000**.

---

## Arranque

```powershell
# Desde la carpeta Qdrant/
py -m uvicorn api.main:app --reload --port 8000
```

**Requiere antes:**
- `OPENAI_API_KEY` configurada en `Qdrant/.env`
- `QDRANT_URL` y `QDRANT_API_KEY` configuradas en `Qdrant/.env`
- Dependencias instaladas: `py -m pip install -r requirements.txt`

**Listo cuando aparece:**
```
INFO:     Application startup complete.
INFO:     Uvicorn running on http://127.0.0.1:8000
```

---

## Funcionalidades

| Función | Descripción breve |
|---------|------------------|
| Ingesta de documentos | Recibe archivos, los divide en chunks, los vectoriza con OpenAI y los guarda en Qdrant |
| Búsqueda semántica | Vectoriza una query y busca los chunks más similares por coseno en Qdrant |
| Listado de documentos | Devuelve todos los archivos indexados con sus metadatos |
| Eliminación de documentos | Borra todos los chunks de un archivo por nombre |
| Health check | Verifica conectividad con Qdrant y retorna estadísticas de la colección |

---

## Endpoints

### `GET /health`

Verifica que el backend esté activo y conectado a Qdrant.

**Input:** ninguno

**Output:** `200 OK`
```json
{
  "status": "ok",
  "collections": ["rag_documents"],
  "active_collection": {
    "name": "rag_documents",
    "points_count": 1240,
    "vectors_count": 1240,
    "status": "green"
  }
}
```

| Campo | Tipo | Descripción |
|-------|------|-------------|
| `status` | `string` | `"ok"` siempre que el servidor responda |
| `collections` | `string[]` | Nombres de colecciones existentes en Qdrant |
| `active_collection.points_count` | `int` | Cantidad de chunks indexados |
| `active_collection.status` | `string` | Estado del cluster Qdrant (`green` / `yellow` / `red`) |

---

### `GET /collection/info`

Metadatos detallados de la colección activa.

**Query params:**

| Parámetro | Tipo | Default | Descripción |
|-----------|------|---------|-------------|
| `mode` | `string` | `"dense"` | Tipo de colección: `dense` o `hybrid` |

**Output:** `200 OK`
```json
{
  "name": "rag_documents",
  "status": "green",
  "vectors_count": 1240,
  "points_count": 1240,
  "indexed_vectors_count": 1240
}
```

**Errores:**
- `404` — la colección no existe

---

### `POST /ingest`

Ingesta archivos enviados como multipart/form-data. Útil para llamadas directas desde scripts o herramientas como Postman.

**Input:** `multipart/form-data`

| Campo | Tipo | Requerido | Descripción |
|-------|------|-----------|-------------|
| `files` | `File[]` | Sí | Uno o más archivos (.pdf, .docx, .txt, .csv, .xlsx, .html, .md, .json) |
| `model_name` | `string` | No | Modelo de embeddings. Default: `text-embedding-3-small` |
| `mode` | `string` | No | `dense` o `hybrid`. Default: `dense` |

**Output:** `200 OK`
```json
{
  "results": [
    {
      "name": "informe.pdf",
      "status": "ok",
      "action": "created",
      "chunks": 87,
      "pages": 12,
      "error": null
    }
  ],
  "total_chunks": 87
}
```

**Valores de `action`:**

| Valor | Significado |
|-------|-------------|
| `created` | Archivo nuevo, indexado correctamente |
| `updated` | Mismo nombre pero contenido distinto — re-indexado |
| `unchanged` | Hash SHA-256 idéntico — no se re-procesó |
| `duplicate` | Mismo contenido ya existe bajo otro nombre — bloqueado |

**Errores:**
- `400` — ningún archivo enviado, extensión no soportada, o archivo corrupto

---

### `POST /ingest/base64`

Ingesta archivos codificados en base64 dentro de un JSON. Es el endpoint que usa el Frontend Gradio.

**Input:** `application/json`

```json
{
  "files": [
    {
      "filename": "informe.pdf",
      "content": "<base64-encoded bytes>"
    }
  ],
  "model_name": "text-embedding-3-small",
  "mode": "dense"
}
```

| Campo | Tipo | Requerido | Descripción |
|-------|------|-----------|-------------|
| `files` | `object[]` | Sí | Lista de archivos con `filename` (string) y `content` (base64 string) |
| `model_name` | `string` | No | Modelo de embeddings. Default: `text-embedding-3-small` |
| `mode` | `string` | No | `dense` o `hybrid`. Default: `dense` |

**Output:** igual que `POST /ingest`

**Errores:**
- `400` — base64 inválido, extensión no soportada, archivo vacío o corrupto

---

### `POST /search`

Busca los chunks más similares a una query usando similitud coseno.

**Input:** `application/json`

```json
{
  "query": "dominios del examen",
  "model_name": "text-embedding-3-small",
  "top_k": 12,
  "mode": "dense",
  "filter": null,
  "min_score": 0.35
}
```

| Campo | Tipo | Requerido | Descripción |
|-------|------|-----------|-------------|
| `query` | `string` | Sí | Texto a buscar (cualquier idioma) |
| `model_name` | `string` | No | Debe coincidir con el modelo usado en la ingesta. Default: `text-embedding-3-small` |
| `top_k` | `int` | No | Máximo de resultados a devolver. Default: `5`, máx: `50` |
| `mode` | `string` | No | `dense` o `hybrid`. Default: `dense` |
| `filter` | `object\|null` | No | Filtro de payload Qdrant (ej: `{"source_file": "doc.pdf"}`). Default: `null` |
| `min_score` | `float` | No | Score mínimo de similitud [0.0–1.0]. Default: `0.35` |

**Output:** `200 OK`
```json
{
  "results": [
    {
      "score": 0.812,
      "text": "Domain 1: Agentic Architecture covers the design of...",
      "source_file": "exam.pdf",
      "section": "Content Outline",
      "page": 2,
      "chunk_index": 14,
      "char_count": 1876,
      "ingested_at": "2026-04-24T18:30:00Z",
      "embedding_model": "text-embedding-3-small",
      "id": "3fa85f64-5717-4562-b3fc-2c963f66afa6"
    }
  ]
}
```

| Campo | Tipo | Descripción |
|-------|------|-------------|
| `score` | `float` | Similitud coseno [0.0–1.0]. Mayor = más relevante |
| `text` | `string` | Contenido del chunk |
| `source_file` | `string` | Nombre del archivo original |
| `section` | `string` | Breadcrumb del heading (puede estar vacío) |
| `page` | `int` | Número de página (1-based) |
| `chunk_index` | `int` | Índice del chunk dentro del documento |
| `char_count` | `int` | Longitud del chunk en caracteres |
| `ingested_at` | `string` | ISO-8601 UTC de cuándo se indexó |
| `embedding_model` | `string` | Modelo usado para generar el vector |
| `id` | `string` | UUID único del punto en Qdrant |

**Errores:**
- `400` — query vacía, `top_k` fuera de rango, `mode` inválido
- `404` — colección no existe (no se han indexado documentos)

---

### `GET /documents`

Lista todos los documentos únicos indexados en la colección, agrupados por archivo.

**Input:** ninguno

**Output:** `200 OK`
```json
{
  "documents": [
    {
      "source_file": "exam.pdf",
      "chunk_count": 87,
      "file_type": "pdf",
      "ingested_at": "2026-04-24T18:30:00Z",
      "embedding_model": "text-embedding-3-small"
    }
  ],
  "total_documents": 1,
  "total_chunks": 87
}
```

| Campo | Tipo | Descripción |
|-------|------|-------------|
| `source_file` | `string` | Nombre del archivo |
| `chunk_count` | `int` | Cantidad de chunks indexados de ese archivo |
| `file_type` | `string` | Extensión sin punto (`pdf`, `docx`, etc.) |
| `ingested_at` | `string` | ISO-8601 UTC de la última ingesta |
| `embedding_model` | `string` | Modelo con el que fue indexado |
| `total_documents` | `int` | Total de archivos únicos |
| `total_chunks` | `int` | Suma de todos los chunks |

---

### `DELETE /documents/{source_file}`

Elimina todos los chunks de un archivo de la colección Qdrant.

**Path param:**

| Parámetro | Tipo | Descripción |
|-----------|------|-------------|
| `source_file` | `string` | Nombre exacto del archivo (ej: `informe.pdf`) |

**Output:** `200 OK`
```json
{
  "source_file": "informe.pdf",
  "deleted": 87
}
```

| Campo | Tipo | Descripción |
|-------|------|-------------|
| `source_file` | `string` | Nombre del archivo eliminado |
| `deleted` | `int` | Cantidad de chunks borrados (0 si no existía) |

---

## Pipeline interno de ingesta

```
Archivo recibido
  → validate_file()          magic bytes + extensión + tamaño ≤ 50MB
  → SHA-256 hash check        4 escenarios: created / updated / unchanged / duplicate
  → load_document()          parser según formato → lista de RawPage
  → chunk_pages()            chunking estructurado + cross-page overlap
  → OpenAIEmbedder.embed()   batches de 32 → API OpenAI text-embedding-3-small
  → QdrantManager.upsert()   vectores + payload → Qdrant Cloud HTTPS
```

## Variables de entorno relevantes (`Qdrant/.env`)

| Variable | Descripción |
|----------|-------------|
| `OPENAI_API_KEY` | API key de OpenAI (requerida) |
| `QDRANT_URL` | URL del cluster Qdrant Cloud |
| `QDRANT_API_KEY` | API key de Qdrant |
| `DENSE_MODEL` | Modelo de embeddings (`text-embedding-3-small`) |
| `DENSE_VECTOR_SIZE` | Dimensiones del vector (`1536`) |
| `CHUNK_SIZE` | Tamaño objetivo de chunks en chars (`2500`) |
| `CHUNK_OVERLAP` | Overlap entre chunks en chars (`400`) |
| `BATCH_SIZE` | Textos por llamada a OpenAI API (`32`) |
