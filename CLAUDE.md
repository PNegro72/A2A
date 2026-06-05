# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Repository Overview

This is a **multi-agent AI recruiting system** (Spanish-language) built with Google ADK + Claude API. A central orchestrator routes recruiter requests to specialized agents: job description parsing, internal/external candidate sourcing, and interview kit generation. A legacy healthcare A2A demo also lives here.

## System Architecture

```
Frontend (Angular 18 PWA :4200)
        │ HTTP + SSE
        ▼
Agente Orchestrator (Google ADK + Claude, :8000)
  - registry/registry.json defines all known agents (no code change needed to add one)
  - tools/call_external_agent.py delegates to agents via HTTP
        │
   ┌────┴──────────────────────────────────┐
   ▼                   ▼                   ▼
Agente               Agente             Agente
Job Description      Busquedas          Entrevistas
(Gemini 2.0 Flash)   Internas           (Claude via LiteLLM)
                  (sentence-            Agente
                  transformers)         Busquedas Externas
                                     (pipeline: Himalayas MCP
                                      + Tavily MCP + GitHub API)
```

**Communication protocols:**
- **A2A protocol (v0.3)**: HTTP-based agent interoperability — all modern agents expose A2A endpoints
- **Google ADK Tools**: intra-agent orchestration via Python tool definitions
- **MCP over HTTP SSE**: external data sources (Himalayas, Tavily)
- **Frontend ↔ Orchestrator**: `POST /chat`, `GET /chat/stream/{request_id}` (SSE), `GET /chat/status/{request_id}` (polling fallback)

## Development Setup

Each agent has its own virtual environment. Root-level `setup_agentes.bat` automates Windows setup.

### Per-Agent Setup

**Orchestrator & Entrevistas** (requirements.txt):
```powershell
pip install -r requirements.txt
```

**Busquedas Internas, Busquedas Externas, Job Description** (pyproject.toml):
```bash
pip install -e ".[dev]"   # includes pytest extras
```

**Frontend**:
```bash
cd frontend && npm install
```

### Running Agents

```bash
# Orchestrator (FastAPI server)
cd agente_orchestrator && python server.py

# Any ADK agent — interactive UI
adk web agentes/<agent_folder>

# Any ADK agent — A2A server (port 8000)
adk web --a2a agentes/<agent_folder>

# Frontend dev server
cd frontend && npm start

# Legacy healthcare agents (separate terminals)
python a2a_policy_agent.py    # :9999
python a2a_provider_agent.py  # :9997
python a2a_research_agent.py  # :9998
python mcpserver.py           # local MCP for provider agent
```

### Tests

```bash
# Busquedas Internas or Entrevistas
pytest tests/ -v

# Single test file
pytest tests/test_agente_busquedas_internas.py -v

# Frontend
cd frontend && npm test
```

## Key Environment Variables

Each agent needs a `.env` file. Copy `.env.example` as a starting point.

| Variable | Used By |
|---|---|
| `CLAUDE_API_KEY` | Orchestrator, Entrevistas |
| `CLAUDE_MODEL` | Orchestrator (default: `claude-sonnet-4-6`) |
| `GOOGLE_API_KEY` | ADK agents (Gemini models) |
| `GEMINI_MODEL` | ADK agents (default: `gemini-2.0-flash`) |
| `GITHUB_TOKEN` | Busquedas Externas |
| `TAVILY_API_KEY` | Busquedas Externas |
| `GOOGLE_APPLICATION_CREDENTIALS` | Legacy healthcare agents (Vertex AI) |
| `OPENAI_API_KEY` | Legacy provider agent |
| `SCHEDULING_AGENT_WEBHOOK_URL` | Orchestrator → n8n scheduling |
| `RECRUITER_EMAIL` | Orchestrator (email drafts) |

Frontend config is in `frontend/src/environments/environment.ts` — set `orchestratorBaseUrl` to point to the running orchestrator.

## Agent Registry Pattern

The orchestrator loads agents from `agente_orchestrator/registry/registry.json`. To add a new agent:
1. Add an entry to `registry.json` with the agent's URL and card URL
2. Set a corresponding env var with the actual URL
3. Add a fallback card in `registry/fallback_cards/` (used if the agent is unreachable)

No orchestrator code changes required.

## Data Models & Persistence

All agents use **Pydantic** for typed I/O. Key shared schemas:
- `JobDescriptionEstructurada` — structured job description (output of job_description agent)
- `ResultadoRanking` / `CandidatoRankeado` — ranked candidate list (output of busquedas_internas)
- `ShortlistReport` / `CandidateLead` — external sourcing results (busquedas_externas)

**Persistence layers:**
- **Busquedas Internas**: `.embeddings_cache.json` alongside `.pptx` CV files; sentence-transformers embeddings
- **Busquedas Externas**: SQLite (`agente_busquedas_externas.db`) for dev; Supabase planned for prod
- **Legacy agents**: `data/doctors.json`, `data/2026AnthemgHIPSBC.pdf`

## Busquedas Externas Pipeline

Sequential 7-stage pipeline for sourcing external candidates:
`IntakeAgent → JDAnalystAgent → PlannerAgent → ParallelAgent(Himalayas + GitHub + Tavily) → DeduplicatorAgent → ScorerAgent → ReportAgent`

Scoring is **evidence-only** (0–1): only observable artifacts (repos, profiles, job titles) contribute — no inference from names or demographics.

## Frontend Architecture

Angular 18 standalone components with Signals. Key structure:
- `core/services/` — orchestrator HTTP client, conversation store, theme
- `features/chat/` — main chat page, message list, bubble, thinking indicator, input
- `shared/` — reusable UI components

Uses Angular service worker for PWA. Production build goes to `dist/frontend/browser/` (Nginx-compatible).

## Python Version Requirements

- Legacy A2A agents: Python 3.10+
- Modern ADK agents (Orchestrator, Busquedas Externas, Entrevistas, Job Description): **Python 3.11+**
- Busquedas Internas: Python 3.11+ (sentence-transformers)
