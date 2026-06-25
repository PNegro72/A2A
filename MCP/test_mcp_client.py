"""
Cliente MCP de prueba — consume el servidor por el PROTOCOLO real (stdio).

A diferencia de verify.py (que importa mcp_server.py como módulo y llama a las
funciones en proceso), este script hace lo mismo que haría el sistema A2A de tu
colega: lanza mcp_server.py como subproceso, hace el handshake MCP por stdio,
lista las herramientas y las invoca con `call_tool`.

Sirve para ver "cómo funciona el MCP" de punta a punta.

Requisitos
----------
  1. El backend RAGaaS corriendo en RAGAAS_URL (ver start-backend.ps1).
  2. MCP/.env configurado (OPENAI_API_KEY, etc.).

Uso
---
    python test_mcp_client.py
    python test_mcp_client.py --query "tu pregunta" --collection rag_documents
"""
from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
from pathlib import Path

from dotenv import load_dotenv
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

HERE = Path(__file__).parent
SERVER = HERE / "mcp_server.py"

# Cargamos MCP/.env acá también y lo inyectamos al subproceso, así el servidor
# recibe OPENAI_API_KEY / RAGAAS_URL aunque se lance desde otro directorio.
load_dotenv(HERE / ".env")


def _result_to_obj(result) -> object:
    """Extrae el valor devuelto por una tool del CallToolResult.

    Las tools devuelven dicts; FastMCP los serializa como TextContent JSON
    (y, en versiones nuevas, también en structuredContent).
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


async def run(query: str, collection: str | None) -> int:
    # El subproceso hereda el entorno actual (incluye lo cargado del .env).
    env = dict(os.environ)
    env["MCP_TRANSPORT"] = "stdio"  # forzamos stdio aunque el .env diga otra cosa

    params = StdioServerParameters(
        command=sys.executable,            # mismo Python que corre este cliente
        args=[str(SERVER)],
        env=env,
    )

    print(f"Lanzando servidor MCP: {sys.executable} {SERVER}")
    print(f"Backend esperado: {os.getenv('RAGAAS_URL', 'http://localhost:8000')}\n")

    async with stdio_client(params) as (read, write):
        async with ClientSession(read, write) as session:
            # ── Handshake del protocolo ──────────────────────────────────────
            await session.initialize()
            print("[OK] Handshake MCP completado.\n")

            # ── Listar tools (lo que vería el agente A2A) ────────────────────
            tools = (await session.list_tools()).tools
            print(f"[1] Tools expuestas ({len(tools)}):")
            for t in tools:
                print(f"      - {t.name}: {(t.description or '').splitlines()[0]}")

            # ── list_collections ─────────────────────────────────────────────
            print("\n[2] call_tool('list_collections') ...")
            try:
                obj = _result_to_obj(await session.call_tool("list_collections", {}))
                cols = (obj or {}).get("collections", [])
                print(f"      OK -> {len(cols)} colección(es): {cols}")
            except Exception as exc:
                print(f"      FALLÓ -> {exc}")
                print("      ¿Está corriendo el backend? Ejecutá start-backend.ps1 primero.")
                return 1

            # ── search ───────────────────────────────────────────────────────
            print(f"\n[3] call_tool('search', query='{query}', collection={collection}) ...")
            args = {"query": query, "top_k": 3}
            if collection:
                args["collection"] = collection
            obj = _result_to_obj(await session.call_tool("search", args))
            results = (obj or {}).get("results", [])
            print(f"      OK -> {len(results)} fragmento(s)")
            for r in results[:3]:
                print(f"        - {r.get('source_file')}  score={r.get('score'):.3f}")
            if not results:
                print("      (Sin fragmentos. ¿La colección tiene documentos indexados?)")

            # ── ask (consume tokens de OpenAI) ───────────────────────────────
            print(f"\n[4] call_tool('ask', query='{query}') ...")
            ask_args = {"query": query, "top_k": 5}
            if collection:
                ask_args["collection"] = collection
            obj = _result_to_obj(await session.call_tool("ask", ask_args)) or {}
            print(f"      OK -> modelo={obj.get('llm_model')}, "
                  f"chunks usados={len(obj.get('chunks_used', []))}")
            print(f"      Respuesta: {str(obj.get('answer', ''))[:300]}")

    print("\n[OK] El MCP respondió por el protocolo real (stdio). Listo para conectar al A2A.")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--query", default="¿De qué tratan los documentos?")
    ap.add_argument("--collection", default=None, help="Colección a consultar.")
    args = ap.parse_args()

    # La consola de Windows suele ser cp1252; forzamos UTF-8 para acentos/emojis.
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

    return asyncio.run(run(args.query, args.collection))


if __name__ == "__main__":
    sys.exit(main())
