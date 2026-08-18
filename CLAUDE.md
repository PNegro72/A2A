# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

> **Coding standards live in [`AGENTS.md`](AGENTS.md).** This file describes *what the system is*;
> `AGENTS.md` describes *how to change it* — skill index, session protocol, and the cross-agent
> change checklist. See [`.harness/README.md`](.harness/README.md) for the harness layout.


## Repository Overview

This is a **multi-agent AI recruiting system** (Spanish-language) built with Google ADK + Claude API. A central orchestrator routes recruiter requests to specialized agents: job description parsing, internal/external candidate sourcing, and interview kit generation.

> **Note (verified 2026-08-04):** an earlier revision of this file documented a legacy healthcare A2A demo (`a2a_policy_agent.py`, `a2a_provider_agent.py`, `a2a_research_agent.py`, `mcpserver.py`, `data/doctors.json`). **None of those files exist in this tree.** References to them have been removed.


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
                                        Agente
                                        Scheduling
                                     (Flask + Google
                                      Calendar OAuth2)
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
```

### Agent ports (verified)

| Port | Agent | Route |
|---|---|---|
| 8000 | orchestrator | `POST /chat`, `GET /chat/stream/{request_id}`, `GET /chat/status/{request_id}`, `GET /health` |
| 8001 | job_description | `POST /a2a/job_description`, `POST /a2a/redactar_jd` |
| 8002 | busquedas_internas | `POST /a2a/busquedas_internas` |
| 8003 | entrevistas (Flask) | `POST /a2a/entrevistas`, `GET /download/<filename>` |
| 8004 | scheduling (Flask) | `POST /scheduling-agent`, `GET /scheduling-agent-card` |
| 8080 | busquedas_externas | `POST /a2a/busquedas_externas` |
| 4200 | frontend | — |

Or start everything at once with `./start_all.sh` (Git Bash) and `./stop_all.sh`.

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
| `GOOGLE_APPLICATION_CREDENTIALS` | (unused — was for the removed healthcare demo) |
| `OPENAI_API_KEY` | Busquedas Externas, Entrevistas (LiteLLM) |
| `AGENT_HTTP_TIMEOUT` | Orchestrator — **required**, no default (`os.environ[...]`); missing value fails at import |
| `CORS_ALLOWED_ORIGINS`, `HOST`, `PORT`, `LOG_LEVEL` | Orchestrator — required at import |
| `REQUEST_STATE_TTL_SECONDS` | Orchestrator — optional, default `600`; TTL of polling state |
| `RUN_TIMEOUT_SECONDS` | Orchestrator — optional, default `600`; caps a polled agent run so a hung run can't make the client poll forever |
| `PENDING_TTL_SECONDS` | Orchestrator — optional, default `900`; discards `request_id`s never claimed by SSE or polling |
| `RAGAAS_MCP_URL` | Busquedas Internas (Qdrant/RAGaaS MCP) |
| `SCHEDULING_AGENT_WEBHOOK_URL` | Orchestrator → Scheduling agent (now the local Python agent at `http://localhost:8004/scheduling-agent`, no longer n8n) |
| `SCHEDULING_AGENT_PORT` | Scheduling agent (default: `8004`) |
| `GOOGLE_CREDENTIALS_FILE` | Scheduling agent (OAuth2 client secrets, default: `credentials.json`) |
| `GOOGLE_TOKEN_FILE` | Scheduling agent (OAuth2 token, default: `token.json`) |
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

## Busquedas Externas Pipeline

Sequential 7-stage pipeline for sourcing external candidates:
`IntakeAgent → JDAnalystAgent → PlannerAgent → ParallelAgent(Himalayas + GitHub + Tavily) → DeduplicatorAgent → ScorerAgent → ReportAgent`

Scoring is **evidence-only** (0–1): only observable artifacts (repos, profiles, job titles) contribute — no inference from names or demographics.

## Frontend Architecture

Angular 18 standalone components with Signals. Key structure:
- `core/services/` — orchestrator HTTP client, conversation store, theme
- `features/chat/` — main chat page, message list, bubble, thinking indicator, input
- `shared/` — reusable UI components

Uses Angular service worker for PWA. `angular.json` sets `outputPath: dist/frontend`; the Angular 18 application builder emits the browser bundle to `dist/frontend/browser/` (Nginx-compatible).

`environment.transportMode` selects `'sse'` (default) or `'polling'`; both backend routes exist. The choice is made at config time — a `request_id` is consumed by the first transport that claims it, so there is no automatic failover between them.

## Python Version Requirements

Declared `requires-python` (verified):

- `agente_job_description`, `agente_busquedas_internas`: **>=3.11**
- `agente_busquedas_externas`: **>=3.12**
- `agente_orchestrator`, `agente_entrevistas`, `agente_scheduling`: none declared (`requirements.txt` only)
