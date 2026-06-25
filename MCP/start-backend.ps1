# Arranca el backend RAGaaS (Qdrant/) en el puerto 8000.
# Este es el ÚNICO servicio que el servidor MCP necesita corriendo de fondo.
# Dejalo abierto en una terminal mientras usás el MCP.

$ErrorActionPreference = "Stop"
$qdrantDir = Join-Path $PSScriptRoot "..\Qdrant"

Write-Host "Levantando backend RAGaaS en http://localhost:8000 ..." -ForegroundColor Cyan
Set-Location $qdrantDir
py -m uvicorn api.main:app --port 8000
