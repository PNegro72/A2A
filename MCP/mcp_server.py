"""
RAGaaS MCP Server
=================

Expone el sistema RAG como un servidor MCP (Model Context Protocol) para que
otro agente / sistema A2A lo consuma como conjunto de herramientas.

Diseño
------
- La RECUPERACIÓN, INGESTA y GESTIÓN de colecciones se delegan al backend RAGaaS
  (la API de la carpeta Qdrant/) vía HTTP. Así se reutiliza toda la lógica ya
  probada (chunking, dedup por hash, validación, etc.).
- La GENERACIÓN de respuesta (LLM) se hace acá mismo, in-process, llamando a
  OpenAI. Esto evita tener que levantar también el servicio Agent/ (puerto 8001).

Por lo tanto, para correr esto solo hacen falta DOS procesos:
    1. El backend RAGaaS (Qdrant/)  →  uvicorn api.main:app --port 8000
    2. Este servidor MCP            →  python mcp_server.py

Transporte
----------
Por defecto usa STDIO (lo que esperan la mayoría de los clientes MCP y frameworks
A2A que "lanzan" el servidor como subproceso). Para exponerlo por red (HTTP),
seteá  MCP_TRANSPORT=http  en el .env  (ver README.md).

Herramientas expuestas
----------------------
    ask                 →  RAG completo: busca + genera respuesta con citas
    search              →  búsqueda semántica (solo fragmentos, sin LLM)
    ingest_document     →  indexa un documento (base64) en una colección
    list_collections    →  lista las colecciones existentes
    create_collection   →  crea una colección vacía
    collection_info     →  metadatos de una colección
    list_documents      →  documentos indexados en una colección
    delete_document     →  borra todos los chunks de un documento
"""
from __future__ import annotations

import base64
import os
from pathlib import Path
from typing import Any, Optional

import httpx
from dotenv import load_dotenv
from mcp.server.fastmcp import FastMCP
from openai import OpenAI, OpenAIError

load_dotenv()

# ── Configuración ─────────────────────────────────────────────────────────────
RAGAAS_URL = os.getenv("RAGAAS_URL", "http://localhost:8000").rstrip("/")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
EMBED_MODEL = os.getenv("EMBED_MODEL", "text-embedding-3-small")

MCP_TRANSPORT = os.getenv("MCP_TRANSPORT", "stdio").lower()
MCP_HOST = os.getenv("MCP_HOST", "127.0.0.1")
MCP_PORT = int(os.getenv("MCP_PORT", "8080"))

HTTP_TIMEOUT = float(os.getenv("RAGAAS_HTTP_TIMEOUT", "120"))

# Prompt de sistema — idéntico al del Agent para que las respuestas sean iguales.
_SYSTEM = (
    "Eres un asistente experto en análisis de documentos. Tu única fuente de información "
    "son los fragmentos de documento que se te proporcionan como contexto, cada uno con su "
    "puntaje de relevancia (score). Reglas estrictas:\n"
    "1. Responde SOLO con información que esté explícitamente en los fragmentos.\n"
    "2. Si un fragmento contiene la respuesta, cítalo indicando su número [N].\n"
    "3. Si ningún fragmento contiene la respuesta, di exactamente: "
    "'No encontré información sobre esto en los documentos disponibles.'\n"
    "4. No especules, no uses conocimiento propio, no inventes datos.\n"
    "5. Responde en el mismo idioma de la pregunta.\n"
)
_MAX_LLM_CHUNKS = 10
_MAX_CHUNK_CHARS = 2500

mcp = FastMCP("ragaas", host=MCP_HOST, port=MCP_PORT)


# ── Helpers internos ──────────────────────────────────────────────────────────
def _post(path: str, json: dict) -> dict:
    with httpx.Client(timeout=HTTP_TIMEOUT) as client:
        resp = client.post(f"{RAGAAS_URL}{path}", json=json)
        resp.raise_for_status()
        return resp.json()


def _get(path: str, params: Optional[dict] = None) -> dict:
    with httpx.Client(timeout=HTTP_TIMEOUT) as client:
        resp = client.get(f"{RAGAAS_URL}{path}", params=params or {})
        resp.raise_for_status()
        return resp.json()


def _search(query: str, top_k: int, min_score: float,
            collection: Optional[str], mode: str = "dense") -> list[dict]:
    payload: dict[str, Any] = {
        "query": query,
        "model_name": EMBED_MODEL,
        "top_k": top_k,
        "mode": mode,
        "min_score": min_score,
    }
    if collection:
        payload["collection"] = collection
    return _post("/search", payload).get("results", [])


def _build_context(chunks: list[dict]) -> str:
    parts = []
    for i, c in enumerate(chunks, 1):
        header = f"[{i}] {c.get('source_file', '—')}"
        if c.get("section"):
            header += f"  ›  {c['section']}"
        if c.get("page"):
            header += f"  (pág. {c['page']})"
        if c.get("score") is not None:
            header += f"  |  relevancia: {c['score']:.3f}"
        parts.append(f"{header}\n{c.get('text', '')[:_MAX_CHUNK_CHARS]}")
    return "\n\n---\n\n".join(parts)


def _generate(query: str, chunks: list[dict], model: str,
              system_prompt: Optional[str]) -> str:
    if not OPENAI_API_KEY:
        raise RuntimeError(
            "OPENAI_API_KEY no está configurada. Definila en MCP/.env antes de usar 'ask'."
        )
    top = chunks[:_MAX_LLM_CHUNKS]
    system = system_prompt.strip() if system_prompt and system_prompt.strip() else _SYSTEM
    user_prompt = (
        f"A continuación se presentan {len(top)} fragmento(s) de documentos "
        f"ordenados por relevancia:\n\n{_build_context(top)}\n\n"
        f"Pregunta: {query}\n\n"
        f"Respuesta (basada exclusivamente en los fragmentos anteriores):"
    )
    client = OpenAI(api_key=OPENAI_API_KEY)
    try:
        completion = client.chat.completions.create(
            model=model,
            temperature=0.1,
            max_tokens=1024,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user_prompt},
            ],
        )
    except OpenAIError as exc:
        raise RuntimeError(f"OpenAI API error: {exc}") from exc
    if not completion.choices:
        raise RuntimeError("OpenAI devolvió una respuesta vacía.")
    return (completion.choices[0].message.content or "").strip()


def _summaries(chunks: list[dict]) -> list[dict]:
    return [
        {
            "index": i + 1,
            "source_file": c.get("source_file", "—"),
            "section": c.get("section", ""),
            "page": str(c.get("page", "")),
            "score": c.get("score"),
            "text_preview": c.get("text", "")[:200],
        }
        for i, c in enumerate(chunks)
    ]


# ── Herramientas MCP ──────────────────────────────────────────────────────────
@mcp.tool()
def ask(
    query: str,
    top_k: int = 15,
    min_score: float = 0.35,
    collection: Optional[str] = None,
    llm_model: Optional[str] = None,
    system_prompt: Optional[str] = None,
) -> dict:
    """Responde una pregunta usando RAG: busca los fragmentos más relevantes en la
    base de conocimiento y genera una respuesta con OpenAI, citando las fuentes.

    Args:
        query: La pregunta en lenguaje natural.
        top_k: Cuántos fragmentos recuperar (1-30).
        min_score: Umbral mínimo de relevancia (0.0-1.0).
        collection: Colección a consultar (si se omite, usa la default).
        llm_model: Modelo de OpenAI a usar (default: gpt-4o-mini).
        system_prompt: Prompt de sistema personalizado (opcional).

    Returns:
        dict con 'answer', 'chunks_used' (fragmentos citados) y 'llm_model'.
    """
    model = llm_model or OPENAI_MODEL
    chunks = _search(query, top_k, min_score, collection)
    if not chunks:
        return {
            "answer": "No encontré información sobre esto en los documentos disponibles.",
            "chunks_used": [],
            "llm_model": model,
        }
    answer = _generate(query, chunks, model, system_prompt)
    return {"answer": answer, "chunks_used": _summaries(chunks), "llm_model": model}


@mcp.tool()
def search(
    query: str,
    top_k: int = 5,
    min_score: float = 0.35,
    collection: Optional[str] = None,
) -> dict:
    """Búsqueda semántica pura: devuelve los fragmentos más relevantes SIN generar
    una respuesta con LLM. Útil cuando el agente que consume quiere los fragmentos
    crudos para razonar por su cuenta.

    Args:
        query: Texto a buscar.
        top_k: Cuántos resultados devolver (1-50).
        min_score: Umbral mínimo de relevancia (0.0-1.0).
        collection: Colección a consultar (si se omite, usa la default).

    Returns:
        dict con 'results': lista de fragmentos con score, texto y metadatos.
    """
    return {"results": _search(query, top_k, min_score, collection)}


@mcp.tool()
def ingest_document(
    filename: str,
    content_base64: str,
    collection: Optional[str] = None,
    chunk_size: Optional[int] = None,
    chunk_overlap: Optional[int] = None,
) -> dict:
    """Indexa un documento en la base de conocimiento. El contenido del archivo se
    envía codificado en base64. Formatos soportados: pdf, docx, txt, xlsx, html, etc.

    Args:
        filename: Nombre del archivo incluyendo extensión (ej. 'informe.pdf').
        content_base64: Bytes del archivo codificados en base64.
        collection: Colección destino (si se omite, usa la default).
        chunk_size: Tamaño de chunk opcional (200-10000).
        chunk_overlap: Solapamiento opcional (>=0 y menor que chunk_size).

    Returns:
        dict con 'results' (estado por archivo) y 'total_chunks' indexados.
    """
    payload: dict[str, Any] = {
        "files": [{"filename": filename, "content": content_base64}],
        "model_name": EMBED_MODEL,
        "mode": "dense",
    }
    if collection:
        payload["collection"] = collection
    if chunk_size is not None:
        payload["chunk_size"] = chunk_size
    if chunk_overlap is not None:
        payload["chunk_overlap"] = chunk_overlap
    return _post("/ingest/base64", payload)


@mcp.tool()
def ingest_local_file(filepath: str, collection: Optional[str] = None) -> dict:
    """Indexa un archivo que ya existe en el disco de la máquina donde corre este
    servidor MCP. Lee el archivo, lo codifica en base64 y lo ingesta.

    Args:
        filepath: Ruta al archivo en el host del servidor MCP.
        collection: Colección destino (si se omite, usa la default).

    Returns:
        dict con 'results' (estado por archivo) y 'total_chunks' indexados.
    """
    p = Path(filepath)
    if not p.is_file():
        raise RuntimeError(f"No existe el archivo: {filepath}")
    content_b64 = base64.b64encode(p.read_bytes()).decode("ascii")
    return ingest_document(filename=p.name, content_base64=content_b64, collection=collection)


@mcp.tool()
def list_collections() -> dict:
    """Lista todas las colecciones disponibles en el clúster de Qdrant.

    Returns:
        dict con 'collections': lista de nombres.
    """
    return _get("/collections")


@mcp.tool()
def create_collection(name: str, mode: str = "dense") -> dict:
    """Crea una colección nueva (vacía). Si ya existe, no hace nada.

    Args:
        name: Nombre de la colección (letras, números, '_' o '-', 1-64 chars).
        mode: 'dense' o 'hybrid'.

    Returns:
        dict con 'name', 'created' (bool) y 'message'.
    """
    return _post("/collections", {"name": name, "mode": mode})


@mcp.tool()
def collection_info(collection: Optional[str] = None, mode: str = "dense") -> dict:
    """Devuelve metadatos de una colección (cantidad de puntos, estado, etc.).

    Args:
        collection: Nombre de la colección (si se omite, usa la default).
        mode: 'dense' o 'hybrid'.

    Returns:
        dict con info de la colección.
    """
    params: dict[str, Any] = {"mode": mode}
    if collection:
        params["collection"] = collection
    return _get("/collection/info", params)


@mcp.tool()
def list_documents(collection: Optional[str] = None) -> dict:
    """Lista los documentos únicos indexados en una colección, con su cantidad de
    chunks, tipo y fecha de ingesta.

    Args:
        collection: Nombre de la colección (si se omite, usa la default).

    Returns:
        dict con 'documents', 'total_documents' y 'total_chunks'.
    """
    params = {"collection": collection} if collection else None
    return _get("/documents", params)


@mcp.tool()
def delete_document(source_file: str, collection: Optional[str] = None) -> dict:
    """Borra todos los chunks de un documento indexado, identificado por su nombre.

    Args:
        source_file: Nombre del documento a borrar (ej. 'informe.pdf').
        collection: Nombre de la colección (si se omite, usa la default).

    Returns:
        dict con 'source_file' y 'deleted' (cantidad de chunks borrados).
    """
    params = {"collection": collection} if collection else None
    with httpx.Client(timeout=HTTP_TIMEOUT) as client:
        resp = client.delete(f"{RAGAAS_URL}/documents/{source_file}", params=params or {})
        resp.raise_for_status()
        return resp.json()


# ── Arranque ──────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    if MCP_TRANSPORT in ("http", "streamable-http"):
        # Expone el MCP por red en http://MCP_HOST:MCP_PORT/mcp
        mcp.run(transport="streamable-http")
    else:
        # stdio: el cliente MCP / sistema A2A lanza este script como subproceso.
        mcp.run(transport="stdio")
