# RAGaaS como MCP — Resumen para integrarlo

Hola 👋 Esto es un sistema **RAG** (búsqueda sobre documentos + respuesta con OpenAI)
expuesto como **servidor MCP** para que lo conectes a tu sistema A2A. No usa Docker,
solo Python. Acá va lo mínimo que necesitás saber; el detalle está en `README.md`.

---

## Qué hace

Expone 9 herramientas MCP. Las más importantes:

| Tool | Qué hace |
|------|----------|
| `ask` | Pregunta en lenguaje natural → busca fragmentos relevantes y devuelve una respuesta generada con citas |
| `search` | Devuelve solo los fragmentos relevantes (sin LLM), por si tu agente quiere razonar él mismo |
| `ingest_document` / `ingest_local_file` | Indexa un documento nuevo (pdf, docx, txt, etc.) |
| `list_collections`, `create_collection`, `collection_info`, `list_documents`, `delete_document` | Gestión de colecciones y documentos |

---

## Qué hay que levantar

Solo **2 procesos** (no hace falta el servicio "Agent"):

1. **Backend RAGaaS** (carpeta `Qdrant/`, puerto 8000) → corre de fondo.
2. **Servidor MCP** (`MCP/mcp_server.py`) → lo lanza tu sistema A2A, o lo corrés en modo HTTP.

El MCP hace la búsqueda/ingesta contra el backend (8000) y la generación con OpenAI por su cuenta.

---

## Puesta en marcha (rápida)

```powershell
# 1. Instalar dependencias (una vez)
cd Qdrant ; py -m pip install -r requirements.txt
cd ..\MCP ; py -m pip install -r requirements.txt
# (en Linux/Mac usá 'python' en vez de 'py')

# 2. Configurar credenciales
#    - Qdrant/.env  -> QDRANT_URL, QDRANT_API_KEY, OPENAI_API_KEY
#    - MCP/.env     -> copiá de MCP/.env.example y poné OPENAI_API_KEY
#    (te paso las claves por separado / ya vienen en los .env del zip)

# 3. Levantar el backend (dejarlo abierto)
.\MCP\start-backend.ps1          # Linux/Mac: bash MCP/start-backend.sh

# 4. Verificar que todo anda (Python puro, sin Node)
cd MCP ; python verify.py --collection rag_documents --query "tu pregunta"
```

Si los 3 chequeos del paso 4 dan OK, está listo para conectar.

---

## Cómo lo conectás a tu sistema A2A

Elegí **un** modo:

### Modo stdio (recomendado — tu sistema lanza el MCP como subproceso)

Registralo en tu config MCP:

```json
{
  "mcpServers": {
    "ragaas": {
      "command": "python",
      "args": ["RUTA/AL/PROYECTO/RAGaaS/MCP/mcp_server.py"],
      "env": {
        "RAGAAS_URL": "http://localhost:8000",
        "OPENAI_API_KEY": "sk-...",
        "OPENAI_MODEL": "gpt-4o-mini",
        "EMBED_MODEL": "text-embedding-3-small"
      }
    }
  }
}
```

(El backend del paso 3 tiene que estar corriendo igual.)

### Modo HTTP (tu sistema se conecta por URL)

```powershell
.\MCP\run-mcp-http.ps1
```

Queda escuchando en **http://127.0.0.1:8080/mcp** → conectate ahí como servidor MCP (streamable-http).

---

## Notas importantes

- `ask` y `search` necesitan que la colección ya tenga documentos. Las colecciones
  disponibles las ves con `list_collections`.
- `EMBED_MODEL` debe coincidir con el modelo usado al indexar
  (por defecto `text-embedding-3-small`).
- Si `ask` no encuentra nada relevante, responde "No encontré información..." en vez de inventar.

Cualquier cosa me escribís. Documentación completa en `MCP/README.md`.
