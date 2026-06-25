# Integrar el RAG a tu front existente

Hola 👋 Vos ya tenés un front. Para sumarle las funciones de este RAG
(elegir colección, subir/borrar documentos, buscar, etc.) **no hay que
recrear nada**: solo conectás tus botones a endpoints que ya existen.

## Cómo está repartido

- **Administración** (colecciones, subir, borrar, listar, buscar fragmentos)
  → backend REST en **`http://localhost:8000`**. Le pegás directo desde el
  front con `fetch`/`axios`. El backend ya tiene **CORS abierto**, así que un
  front en el navegador lo puede llamar sin configurar nada extra.
- **Respuesta generada con LLM y citas** (el "chat") → eso **no** está en el
  REST: vive en el servidor MCP (`MCP/mcp_server.py`). Lo maneja tu agente A2A
  llamando a la herramienta `ask`. El front no genera respuestas por su cuenta.

> Resumen mental: **botones de administración → REST 8000. El chat que
> responde → el agente A2A vía la tool `ask`.**

---

## Mapa: control del front → endpoint

Base URL: `http://localhost:8000`

| Control en el front | Método + endpoint | Body / params |
|---|---|---|
| Poblar el dropdown de colecciones | `GET /collections` | → `{ collections: [...] }` |
| Crear colección | `POST /collections` | `{ "name": "X", "mode": "dense" }` |
| Info / conteo de una colección | `GET /collection/info?collection=X` | → puntos, estado |
| Listar documentos de una colección | `GET /documents?collection=X` | → `{ documents, total_documents, total_chunks }` |
| Subir archivo (form clásico) | `POST /ingest` | multipart: `files[]`, `collection` |
| Subir archivo (JSON base64) | `POST /ingest/base64` | `{ files:[{filename,content}], collection }` |
| Borrar documento | `DELETE /documents/{source_file}?collection=X` | → `{ deleted: N }` |
| Buscar fragmentos (preview sin LLM) | `POST /search` | `{ query, collection, top_k, min_score }` |
| Respuesta generada (chat) | tool MCP `ask` vía A2A | `{ query, collection }` — ⚠️ no es REST |

---

## El flujo de "elegir colección y que responda en base a esa"

1. El front llama `GET /collections` y llena el dropdown.
2. El usuario elige una (ej. `rag_documents`). El front la guarda en una variable.
3. Para administrar (subir/borrar/listar) → manda esa colección en el parámetro
   `collection`.
4. Para el chat → el front le pasa la colección elegida al agente A2A, y el
   agente llama `ask(query, collection="rag_documents")`. La respuesta sale
   **solo** de esa colección.

---

## Ejemplos `fetch` listos para copiar

```js
const RAG_URL = "http://localhost:8000";

// 1) Llenar el dropdown de colecciones
async function getCollections() {
  const r = await fetch(`${RAG_URL}/collections`);
  const { collections } = await r.json();
  return collections; // ["rag_documents", ...]
}

// 2) Crear una colección nueva
async function createCollection(name) {
  const r = await fetch(`${RAG_URL}/collections`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ name, mode: "dense" }),
  });
  return r.json(); // { name, created, message }
}

// 3) Listar documentos de la colección elegida
async function listDocuments(collection) {
  const r = await fetch(`${RAG_URL}/documents?collection=${encodeURIComponent(collection)}`);
  return r.json(); // { documents, total_documents, total_chunks }
}

// 4) Subir un archivo a la colección elegida (form clásico)
async function uploadFile(file, collection) {
  const fd = new FormData();
  fd.append("files", file);            // input type="file"
  fd.append("collection", collection);
  const r = await fetch(`${RAG_URL}/ingest`, { method: "POST", body: fd });
  return r.json(); // { results, total_chunks }
}

// 5) Borrar un documento de la colección elegida
async function deleteDocument(sourceFile, collection) {
  const url = `${RAG_URL}/documents/${encodeURIComponent(sourceFile)}`
            + `?collection=${encodeURIComponent(collection)}`;
  const r = await fetch(url, { method: "DELETE" });
  return r.json(); // { source_file, deleted }
}

// 6) Buscar fragmentos (preview, sin LLM)
async function search(query, collection) {
  const r = await fetch(`${RAG_URL}/search`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ query, collection, top_k: 5, min_score: 0.35 }),
  });
  return r.json(); // { results: [...] }
}
```

Para el **chat con respuesta generada**, no llamás al REST: tu agente A2A
invoca la tool `ask` del MCP, pasándole `query` y la `collection` elegida.

---

## Antes de probar

1. El backend tiene que estar corriendo (puerto 8000): `MCP/start-backend.ps1`.
2. Probá la API a mano abriendo `http://localhost:8000/docs` (Swagger) — ahí
   ves y disparás todos los endpoints sin escribir código.
3. Las colecciones disponibles y sus datos ya viven en Qdrant Cloud (vienen en
   los `.env`), así que `GET /collections` debería devolver `rag_documents`
   apenas levantes el backend.
