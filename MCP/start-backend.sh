#!/usr/bin/env bash
# Arranca el backend RAGaaS (Qdrant/) en el puerto 8000.
# Este es el ÚNICO servicio que el servidor MCP necesita corriendo de fondo.
# Dejalo abierto en una terminal mientras usás el MCP.
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR/../Qdrant"

echo "Levantando backend RAGaaS en http://localhost:8000 ..."
python -m uvicorn api.main:app --port 8000
