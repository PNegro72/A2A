"""
Cliente MCP (read-only) del servidor RAGaaS.

Esta es la ÚNICA pieza del agente que habla el protocolo MCP. Consume la tool
`search` del servidor MCP de la carpeta `MCP/` por transporte HTTP streamable
(``http://127.0.0.1:8080/mcp`` por defecto). Ese servidor MCP, a su vez, proxea
la búsqueda semántica contra el backend RAGaaS/Qdrant.

El agente solo CONSUME: usa exclusivamente `search` (búsqueda semántica que
devuelve fragmentos crudos). No ingesta ni borra documentos.

El resto del agente trabaja con dicts/Pydantic planos: este módulo traduce el
``CallToolResult`` de MCP a una lista de chunks (dicts).
"""
from __future__ import annotations

import json
import logging
from typing import Any, Optional

from mcp import ClientSession
from mcp.client.streamable_http import streamablehttp_client

logger = logging.getLogger(__name__)


def _result_to_obj(result: Any) -> Any:
    """Extrae el valor devuelto por una tool de un ``CallToolResult``.

    Las tools de FastMCP devuelven dicts que se serializan como ``TextContent``
    JSON y, en versiones nuevas, también en ``structuredContent``. Replicamos la
    lógica del cliente de prueba oficial del MCP (``MCP/test_mcp_client.py``).
    """
    structured = getattr(result, "structuredContent", None)
    if structured:
        return structured
    for block in getattr(result, "content", []) or []:
        text = getattr(block, "text", None)
        if text is None:
            continue
        try:
            return json.loads(text)
        except (json.JSONDecodeError, TypeError):
            return text
    return None


async def buscar_chunks(
    *,
    mcp_url: str,
    query: str,
    top_k: int,
    min_score: float,
    collection: Optional[str],
) -> list[dict]:
    """Llama a la tool ``search`` del MCP y devuelve la lista de chunks crudos.

    Cada chunk es un dict con la forma:
        {score, text, source_file, section, page, chunk_index, ...}

    Args:
        mcp_url: URL del servidor MCP (endpoint streamable-http, ej. ``/mcp``).
        query: Texto a buscar (se arma a partir de la Job Description).
        top_k: Cantidad máxima de fragmentos a recuperar (1–50 según el MCP).
        min_score: Umbral mínimo de similitud [0.0–1.0].
        collection: Colección de Qdrant a consultar (None usa la default del MCP).

    Returns:
        Lista de chunks (posiblemente vacía) ordenada por relevancia.

    Raises:
        Exception: si no se puede conectar al MCP/backend o la tool falla.
    """
    args: dict[str, Any] = {"query": query, "top_k": top_k, "min_score": min_score}
    if collection:
        args["collection"] = collection

    async with streamablehttp_client(mcp_url) as (read, write, _):
        async with ClientSession(read, write) as session:
            await session.initialize()
            result = await session.call_tool("search", args)

            if getattr(result, "isError", False):
                raise RuntimeError(
                    f"La tool 'search' del MCP devolvió un error para la query."
                )

            obj = _result_to_obj(result) or {}
            results = obj.get("results", []) if isinstance(obj, dict) else []
            logger.info(
                "buscar_chunks | MCP %s -> %s chunk(s) (collection=%s, top_k=%s)",
                mcp_url, len(results), collection, top_k,
            )
            return results
