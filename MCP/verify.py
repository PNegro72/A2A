"""
Verificación end-to-end del servidor MCP — sin Node, solo Python.

Importa el servidor MCP y llama a sus herramientas contra el backend RAGaaS real.
Requiere:
  1. El backend corriendo en RAGAAS_URL (ver start-backend.ps1).
  2. MCP/.env configurado con OPENAI_API_KEY.

Uso:
    python verify.py
    python verify.py --query "tu pregunta"   (opcional)
"""
from __future__ import annotations

import argparse
import importlib.util
import sys
from pathlib import Path

HERE = Path(__file__).parent


def _load_server():
    spec = importlib.util.spec_from_file_location("mcp_server", HERE / "mcp_server.py")
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


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

    m = _load_server()
    print(f"Backend configurado: {m.RAGAAS_URL}")
    print(f"OPENAI_API_KEY presente: {bool(m.OPENAI_API_KEY)}\n")

    # 1) list_collections
    print("[1] list_collections ...")
    try:
        cols = m.list_collections().get("collections", [])
        print(f"    OK -> {len(cols)} colección(es): {cols}")
    except Exception as exc:
        print(f"    FALLÓ -> {exc}")
        print("    ¿Está corriendo el backend? Ejecutá start-backend.ps1 primero.")
        return 1

    # 2) search
    print(f"\n[2] search('{args.query}', collection={args.collection}) ...")
    try:
        results = m.search(args.query, top_k=3, collection=args.collection).get("results", [])
        print(f"    OK -> {len(results)} fragmento(s)")
        for r in results[:3]:
            print(f"      - {r.get('source_file')}  score={r.get('score'):.3f}")
        if not results:
            print("    (No hay fragmentos. ¿La colección tiene documentos indexados?)")
    except Exception as exc:
        print(f"    FALLÓ -> {exc}")
        return 1

    # 3) ask (consume tokens de OpenAI)
    print(f"\n[3] ask('{args.query}') ...")
    try:
        res = m.ask(args.query, top_k=5, collection=args.collection)
        print(f"    OK -> modelo={res['llm_model']}, chunks usados={len(res['chunks_used'])}")
        print(f"    Respuesta: {res['answer'][:300]}")
    except Exception as exc:
        print(f"    FALLÓ -> {exc}")
        return 1

    print("\n[OK] Verificación completa: las tools del MCP funcionan contra el backend real.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
