# Corre el servidor MCP en modo HTTP (transporte streamable-http).
# Usá esto SOLO si el sistema A2A consume el MCP por red en lugar de lanzarlo
# como subproceso (stdio). El backend (start-backend.ps1) debe estar corriendo.

$ErrorActionPreference = "Stop"
$env:MCP_TRANSPORT = "http"
Set-Location $PSScriptRoot
py mcp_server.py
