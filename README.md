# A2A Healthcare Agents

Proyecto de prueba y aprendizaje para implementar el protocolo A2A con varios agentes orientados al dominio de salud.

El repositorio incluye:

- Un agente de polizas que responde preguntas usando un PDF de cobertura.
- Un agente de prestadores que consulta un servidor MCP con un dataset local de medicos.
- Un agente de investigacion que usa busqueda web con Google ADK.
- Notebooks para orquestacion y pruebas manuales.

## Estructura

- `a2a_policy_agent.py`: expone el agente de polizas como servicio A2A.
- `a2a_provider_agent.py`: expone el agente de prestadores como servicio A2A.
- `a2a_research_agent.py`: expone el agente de investigacion como servicio A2A.
- `policy_agent.py`: logica del agente que consulta el PDF de cobertura.
- `provider_agent.py`: logica del agente que usa herramientas MCP para buscar medicos.
- `mcpserver.py`: servidor MCP con la herramienta `list_doctors`.
- `data/doctors.json`: dataset local de prestadores.
- `data/2026AnthemgHIPSBC.pdf`: documento base para preguntas de cobertura.
- `orchestrator.ipynb`, `mcptester.ipynb`, `test.ipynb`: notebooks de exploracion y pruebas.

## Requisitos

- Python 3.10 o superior.
- Credenciales para OpenAI o endpoint compatible para el agente de prestadores.
- Credenciales de Google Cloud / Vertex AI para el agente de polizas.
- `GOOGLE_API_KEY` para el agente de investigacion.

Instalacion:

```powershell
python -m venv a2a_env
.\a2a_env\Scripts\activate
pip install -r requirements.txt
```

## Variables de entorno

Crear un archivo `.env` con valores similares a estos:

```env
AGENT_HOST=localhost
POLICY_AGENT_PORT=9999
PROVIDER_AGENT_PORT=9997
RESEARCH_AGENT_PORT=9998

OPENAI_API_KEY=your-openai-key
OPENAI_BASE_URL=https://api.openai.com/v1

GOOGLE_APPLICATION_CREDENTIALS=path\to\service-account.json
GOOGLE_CLOUD_PROJECT=your-gcp-project-id
GOOGLE_CLOUD_LOCATION=us-central1
GOOGLE_API_KEY=your-google-api-key
```

Notas:

- `policy_agent.py` usa `GOOGLE_APPLICATION_CREDENTIALS`, `GOOGLE_CLOUD_PROJECT` y opcionalmente `GOOGLE_CLOUD_LOCATION`.
- `provider_agent.py` usa `OPENAI_API_KEY` y `OPENAI_BASE_URL`.
- `a2a_research_agent.py` usa `GOOGLE_API_KEY`.

## Ejecucion

Levantar cada agente en una terminal distinta:

```powershell
python a2a_policy_agent.py
```

```powershell
python a2a_provider_agent.py
```

```powershell
python a2a_research_agent.py
```

El servidor MCP usado por el agente de prestadores se inicia automaticamente via `provider_agent.py`, pero tambien se puede probar de forma aislada:

```powershell
python mcpserver.py
```

## Capacidades actuales

### Policy Agent

Responde preguntas sobre cobertura de seguros usando el PDF `data/2026AnthemgHIPSBC.pdf`.

Ejemplos:

- `What does this policy cover for mental health services?`
- `Do I need a referral for specialist care?`

### Provider Agent

Busca medicos por ciudad y/o estado usando el dataset local `data/doctors.json` a traves de una herramienta MCP.

Ejemplos:

- `Find a psychiatrist in Boston, MA`
- `List doctors in CA`

### Research Agent

Hace investigacion web orientada a salud usando Google ADK y `google_search`.

Ejemplos:

- `What are the latest treatment options for insomnia?`
- `What symptoms are associated with thyroid disorders?`

## Desarrollo

- Los archivos sensibles y entornos locales estan excluidos por `.gitignore`.
- Los notebooks se usan como entorno de pruebas y orquestacion.
- El proyecto mezcla integraciones A2A, MCP, LangChain y Vertex AI, por lo que conviene validar credenciales antes de probar cada agente.
