# Agentes de Reclutamiento — Sistema Multi-Agente A2A

Parte del sistema multi-agente A2A para reclutamiento. Contiene dos agentes construidos con [Google ADK](https://google.github.io/adk-docs/):

| Agente | Responsabilidad | Estado |
|--------|----------------|--------|
| **Agente Job Description** | Recibe un JD en texto libre y lo devuelve estructurado (role_title, role_description, management_level, skills) | Listo |
| **Agente Búsquedas Internas** | Busca candidatos internos en Workday y los rankea con IA. Retorna un ResultadoRanking al orquestador | Listo (fuente local PPTX) |

## Arquitectura del flujo

```
Orquestador (equipo externo)
   │
   ├─► Agente Job Description
   │       Input:  JD en texto libre
   │       Output: JobDescriptionEstructurada (JSON)
   │       Modelo: Gemini 2.0 Flash (sin tools externas)
   │
   └─► Agente Búsquedas Internas
           Input:  JobDescriptionEstructurada
           Output: ResultadoRanking (JSON)
           Tools:
             └─ consultar_ats       → Workday API   [STUB → local PPTX]
```

## Estructura del proyecto

```
agente_busquedas_internas/
├── agentes/
│   ├── schemas.py                              # Modelos Pydantic compartidos
│   ├── config/
│   │   └── settings.py                         # Variables de entorno (pydantic-settings)
│   ├── job_description/
│   │   ├── __init__.py                         # Exporta `agent` (convención ADK)
│   │   ├── agent.py                            # Definición del agente ADK
│   │   └── prompts.py                          # Prompt del sistema
│   └── busquedas_internas/
│       ├── __init__.py                         # Exporta `agent` (convención ADK)
│       ├── agent.py                            # Definición del agente ADK
│       ├── agent-prompt.txt                    # Prompt del sistema
│       ├── cvs.py                              # Lectura y búsqueda semántica de CVs (.pptx)
│       ├── workday_api_service.py              # Placeholder integración Workday [STUB]
│       └── tools/
│           └── consultar_ats.py                # Herramienta ATS (delega en cvs.py)
├── tests/
│   ├── conftest.py
│   ├── test_agente_job_description.py
│   └── test_agente_busquedas_internas.py
├── .env.example
├── pyproject.toml
└── README.md
```

## Setup

### Prerequisitos

- Python 3.11+
- WSL (Ubuntu recomendado) o Linux/macOS

### 1. Clonar e instalar dependencias

```bash
# Crear entorno virtual
python -m venv .venv
source .venv/bin/activate

# Instalar en modo editable con dependencias de desarrollo
pip install -e ".[dev]"
```

Con `uv` (más rápido):

```bash
pip install uv
uv sync --extra dev
```

### 2. Configurar variables de entorno

```bash
cp .env.example .env
```

Editar `.env` con las credenciales reales. Ver comentarios en `.env.example`.
Las variables de Workday están **pendientes de confirmación con Pablo**.

### 3. Correr los tests

```bash
# Todos los tests (no requieren APIs externas)
pytest tests/ -v

# Solo un módulo
pytest tests/test_agente_busquedas_internas.py -v
```

### 4. Probar los agentes con ADK Web UI

```bash
# Agente Job Description
adk web agentes/job_description

# Agente Búsquedas Internas
adk web agentes/busquedas_internas
```

O con el runner de consola:

```bash
adk run agentes/job_description
```

## Modelos de datos

Los modelos Pydantic están en `agentes/schemas.py`:

- `JobDescriptionEstructurada`: output del Agente JD, input del Agente Búsquedas.
- `Candidato`: perfil de un empleado interno (normalizado desde Workday).
- `CandidatoRankeado`: candidato con score y justificación del LLM.
- `ResultadoRanking`: resultado completo del proceso de búsqueda.

## Pendientes

- [ ] Reunión con Pablo: confirmar endpoints, auth y formato de respuesta de Workday API
- [ ] Implementar `workday_api_service.py`: integración real con Workday OAuth2
- [ ] Integrar con el orquestador del equipo (definir contrato de mensajes A2A)
- [ ] Agregar tests de integración (con mocks de las APIs externas)
