# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

```bash
# Setup (desde agente_busquedas_internas/)
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
# o con uv: pip install uv && uv sync --extra dev

# Levantar el agente con ADK (UI de desarrollo interactiva)
adk web agentes/busquedas_internas

# Levantar el agente expuesto como servidor A2A (para integración con orquestador)
# Inicia un servidor en http://localhost:8000 con endpoints:
#   POST /run          → ejecutar el agente
#   GET  /.well-known/agent.json → AgentCard
adk web --a2a agentes/busquedas_internas

# Tests (no requieren APIs externas)
pytest tests/ -v
pytest tests/test_agente_busquedas_internas.py -v   # módulo específico
```

## Arquitectura

Agente ADK para búsqueda y ranking de candidatos internos en reclutamiento.
Es un `LlmAgent` (google-adk) que puede exponerse como servidor A2A
mediante `adk web --a2a`.

El agente de parseo de Job Descriptions vive en `../agente_job_description/`.

```
Orquestador externo (usa RemoteA2aAgent para conectar)
    │
    └─► Agente busquedas_internas/   →  :8000/a2a/busquedas_internas
        Input:  JobDescriptionEstructurada (JSON)
        Output: ResultadoRanking (JSON)
        Tipo:   LlmAgent con output_schema=ResultadoRanking
        Tools:
          └─ consultar_ats               → Workday API  [STUB]
        Nota:  el ranking lo realiza el LLM directamente (sin tool separada)
        Nota:  la persistencia en Supabase es responsabilidad del orquestador
```

### Convención ADK por módulo

ADK requiere esta estructura para cada agente:

| Archivo | Rol |
|---|---|
| `agent.py` | Define `root_agent = LlmAgent(...)` |
| `__init__.py` | `from . import agent` (ADK busca `agent.root_agent`) |
| `agent.json` | AgentCard estático (nombre, URL, skills, capabilities) |
| `agent-prompt.txt` | Instrucción del sistema, leída en `agent.py` con `_read_prompt()` |

### Modelos de datos compartidos (`agentes/schemas.py`)

- `JobDescriptionEstructurada` — output del Agente 1, input del Agente 2
- `Candidato` — perfil de empleado interno del ATS
- `CandidatoRankeado` — score (0.0–1.0) + justificación + análisis de skills
- `ResultadoRanking` — resultado final: estado, candidatos rankeados, timestamp

### Por qué no existe `rankear_candidatos` como tool

En el diseño original (a2a-sdk), `rankear_candidatos` era una función que llamaba
a Gemini internamente. En ADK, el `LlmAgent` de `busquedas_internas` ES Gemini:
delegar el ranking a otra llamada al mismo modelo sería redundante. El ranking
ocurre directamente en el `output_schema=ResultadoRanking` del agente.

## Configuración

Copiar `.env.example` a `.env`. Variables requeridas:
- `GOOGLE_API_KEY` — Google AI Studio (leída por `load_dotenv()` en cada agent.py)
- `GEMINI_MODEL` — default `gemini-2.0-flash`
- `WORKDAY_API_URL`, `WORKDAY_TENANT`, `WORKDAY_CLIENT_ID`, `WORKDAY_CLIENT_SECRET`, `WORKDAY_TOKEN_URL`

Config cargada con pydantic-settings en `agentes/config/settings.py` via `get_settings()` (LRU-cached).
Cada `agent.py` llama a `load_dotenv()` explícitamente porque pydantic-settings no escribe
en `os.environ` y ADK necesita `GOOGLE_API_KEY` allí para autenticar con Gemini.

## Stubs pendientes

Una integración retorna datos mock, bloqueada en info de Pablo:
- **Workday** (`workday_api_service.py`): endpoints, OAuth2, formato de respuesta

## Convenciones de skills

- Hard skills / tecnologías: PascalCase — `Python`, `FastAPI`, `AWS`
- Soft skills: minúsculas en español — `liderazgo`, `comunicación efectiva`
- Nivel de management: elegir el más bajo ante ambigüedad
