# RAGaaS — Servidor MCP

Expone el sistema RAG como un **servidor MCP** (Model Context Protocol) para que
otro agente o sistema **A2A** lo consuma como un conjunto de herramientas.

No usa Docker. Solo Python.

---

## Qué hace falta levantar

Solo **dos** cosas:

| # | Componente | Cómo se levanta |
|---|-----------|-----------------|
| 1 | **Backend RAGaaS** (carpeta `Qdrant/`, puerto 8000) | corre de fondo en una terminal |
| 2 | **Servidor MCP** (`mcp_server.py`) | lo lanza tu sistema A2A (stdio) **o** se corre en modo HTTP |

> El servidor MCP hace la **búsqueda/ingesta** contra el backend (8000) y la
> **generación de respuesta** (OpenAI) por su cuenta. Por eso **no** hace falta
> levantar el servicio `Agent/` (8001).

---

## Instalación (una sola vez)

```powershell
# Desde la raíz del proyecto RAGaaS

# 1. Dependencias del backend
cd Qdrant
py -m pip install -r requirements.txt

# 2. Dependencias del MCP
cd ..\MCP
py -m pip install -r requirements.txt
```

En Linux/Mac usá `python` en lugar de `py`.

---

## Configuración

Hay que crear **dos** archivos `.env` a partir de los `.env.example`:

**`Qdrant/.env`** — credenciales de Qdrant Cloud + OpenAI (para embeddings):

```
QDRANT_URL=https://...
QDRANT_API_KEY=...
OPENAI_API_KEY=sk-...
```

**`MCP/.env`** — copia de `MCP/.env.example`:

```
RAGAAS_URL=http://localhost:8000
OPENAI_API_KEY=sk-...        # misma key de OpenAI
OPENAI_MODEL=gpt-4o-mini
EMBED_MODEL=text-embedding-3-small
MCP_TRANSPORT=stdio
```

---

## Arranque

### 1. Levantar el backend (siempre)

```powershell
# Windows
.\MCP\start-backend.ps1
```
```bash
# Linux / Mac
bash MCP/start-backend.sh
```

Dejalo corriendo. Probá que responde abriendo http://localhost:8000/docs

### 2. Conectar el servidor MCP — elegí UN modo

#### Modo A — stdio (recomendado, el sistema A2A lo lanza)

Registrá el servidor en la config MCP de tu sistema/cliente. Ejemplo de bloque
de configuración (formato típico estilo Claude Desktop / clientes MCP):

```json
{
  "mcpServers": {
    "ragaas": {
      "command": "python",
      "args": ["C:/ruta/al/proyecto/RAGaaS/MCP/mcp_server.py"],
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

El cliente lanza `mcp_server.py` solo cuando lo necesita. (El backend del paso 1
debe estar corriendo igual.)

#### Modo B — HTTP (el sistema A2A se conecta por URL)

```powershell
# Windows
.\MCP\run-mcp-http.ps1
```
```bash
# Linux / Mac
MCP_TRANSPORT=http python MCP/mcp_server.py
```

El MCP queda escuchando en **http://127.0.0.1:8080/mcp**. Tu sistema A2A se
conecta a esa URL como servidor MCP por streamable-http.

---

## Herramientas expuestas

| Tool | Qué hace |
|------|----------|
| `ask` | RAG completo: busca fragmentos + genera respuesta con citas `[N]` |
| `search` | Búsqueda semántica pura (fragmentos crudos, sin LLM) |
| `ingest_document` | Indexa un documento enviado en base64 |
| `ingest_local_file` | Indexa un archivo del disco del host del MCP |
| `list_collections` | Lista las colecciones |
| `create_collection` | Crea una colección vacía |
| `collection_info` | Metadatos de una colección |
| `list_documents` | Documentos indexados en una colección |
| `delete_document` | Borra todos los chunks de un documento |

---

## Verificar que funciona

Con el backend corriendo, ejecutá el script de verificación (Python puro, sin Node):

```powershell
cd MCP
python verify.py --collection rag_documents --query "tu pregunta"
```

Llama a `list_collections`, `search` y `ask` contra el backend real y muestra el
resultado. Si las tres dan OK, el MCP está listo.

> Alternativa con UI (requiere Node.js instalado):
> `npx @modelcontextprotocol/inspector python MCP/mcp_server.py`

---

## Notas

- `ask` y `search` requieren que la colección ya tenga documentos indexados.
- El `EMBED_MODEL` del MCP debe coincidir con el modelo usado al indexar
  (por defecto `text-embedding-3-small`, 1536 dims).
- Si `ask` no encuentra nada por encima de `min_score`, devuelve el mensaje
  estándar "No encontré información..." en vez de inventar.
