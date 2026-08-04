---
name: python-adk-agents
description: "Google ADK + A2A agent conventions for this repo: real agent layouts, the POST /a2a/<name> webhook contract, orchestrator delegation, domain models, MCP clients, and evidence-only scoring. Use when touching any agente_*/ package."
when_to_use: "Writing or reviewing code under agente_orchestrator/, agente_job_description/, agente_busquedas_internas/, agente_busquedas_externas/, agente_entrevistas/, agente_scheduling/."
user-invocable: false
model: sonnet
---

# Skill: Python — ADK / A2A Agents

Extends `code-python`. Load both. Everything below was verified against the tree on 2026-08-04.

## Actual agent map — do not assume a uniform layout

| Agent | Port | Server | Layout | Missing |
|---|---|---|---|---|
| `agente_orchestrator` | 8000 | FastAPI | root `agent.py`, `server.py`, `prompts/`, `tools/`, `registry/` | no `tests/` |
| `agente_job_description` | 8001 | FastAPI | `agentes/job_description/`, `agentes/redactar_jd/`, `schemas/`, `tests/` | no root `prompts/`, no root `tools/` |
| `agente_busquedas_internas` | 8002 | FastAPI | `agentes/busquedas_internas/` (tools nested inside), `agentes/config/`, `schemas/`, `tests/` | no root `prompts/` |
| `agente_entrevistas` | 8003 | **Flask** | root `agent.py`, `models/`, `prompts/`, `tools/`, `utils/`, `tests/`, `pytest.ini` | — |
| `agente_scheduling` | 8004 | **Flask** | `server.py`, `calendar_service.py`, `models.py`, `setup_oauth.py` | no ADK agent, no `tools/`, no `tests/` |
| `agente_busquedas_externas` | 8080 | FastAPI | `src/agents/`, `src/domain/`, `src/persistence/`, `tests/unit/` | uses `src/`, not `agentes/` |

**When adding to an existing agent, follow that agent's layout.** When creating a new agent, use the
`agentes/<name>/` + `schemas/` + `tests/` shape (job_description / busquedas_internas) — it is the
closest thing to a house style. Do not "fix" another agent's layout as a side effect of a change.

## A2A webhook contract

Every agent exposes `POST /a2a/<agent_name>` plus `GET /health`. Exceptions to know:

- `agente_job_description` exposes **two**: `/a2a/job_description` and `/a2a/redactar_jd`
- `agente_scheduling` deviates: `POST /scheduling-agent` and `GET /scheduling-agent-card`
- `agente_entrevistas` also serves `GET /download/<filename>`

REQUIRE:
- A new capability on an existing agent is a new action inside its existing `/a2a/<name>` handler,
  not a new top-level route — the fallback cards route on `actions`, not on paths
- `GET /health` on every agent; `start_all.sh` and `stop_all.sh` depend on it

## Orchestrator delegation

Delegation goes through `agente_orchestrator/tools/call_external_agent.py`:

```python
def call_external_agent(agent_name: str, payload: dict) -> dict:
```

It is **synchronous** — `requests.post(webhook_url, json=payload, timeout=AGENT_HTTP_TIMEOUT)` — and
`AGENT_HTTP_TIMEOUT` is read as `os.environ["AGENT_HTTP_TIMEOUT"]`, so it is **required**: the
orchestrator fails at import if it is missing. Keep it in `.env.example`.

REJECT if:
- A second HTTP client for delegation is hand-rolled instead of using `call_external_agent`
- An agent imports another agent's Python modules directly instead of calling it over HTTP
- A downstream failure escapes as a stack trace — `call_external_agent` already maps `Timeout` /
  `ConnectionError` / `RequestException` to a structured dict; preserve that shape
- `AGENT_HTTP_TIMEOUT` is given a silent default

## Orchestrator HTTP contract

| Route | Status |
|---|---|
| `POST /chat` → `ChatInitResponse` | implemented (`server.py`) |
| `GET /chat/stream/{request_id}` (SSE) | implemented |
| `GET /chat/status/{request_id}` (polling) | implemented |
| `GET /health` | implemented |

Both transports are fed by one generator, `_run_agent_events()`. Do not duplicate the ADK event
loop — add new event types there and both transports get them.

**A `request_id` is consumed by exactly one transport.** Whichever endpoint claims it first (SSE or
the first `/chat/status` poll) starts the agent run; the other then returns 404. This is why there
is no automatic SSE→polling failover in the client: by the time SSE fails, the id is already spent.
Choose the transport up front via `environment.transportMode`.

Polling state lives in `request_state.py` (`RequestStateStore`) — deliberately free of ADK and
FastAPI imports so it is testable without the stack. On each `POST /chat` the server purges
finished states past `REQUEST_STATE_TTL_SECONDS` (600), runs stuck in `running` past the store's
`max_running_seconds` (1800), and `pending_requests` never claimed by any transport past
`PENDING_TTL_SECONDS` (900).

**Polling has no client disconnect.** SSE cancels a run when the browser goes away; a polled run has
nothing to cancel it, so every background run is bounded by `RUN_TIMEOUT_SECONDS` (600) and
surfaces as `RUN_TIMEOUT`.

REJECT if:
- A run that ends without a final response leaves `status: running` — the client would poll forever.
  `RequestStateStore.finish()` closes it as `NO_FINAL_RESPONSE`
- Raw exception text reaches the client. `_run_agent_events` logs the detail and emits the generic
  `ORCHESTRATOR_ERROR_MESSAGE`
- A background run is launched with a bare `asyncio.create_task(...)`. The event loop keeps only a
  weak reference; hold it in `_background_tasks` and drop it with `add_done_callback`
- Anything unbounded is added to `pending_requests` or `request_states`. Both hold user data
  (including base64 CVs) and both are purged on `POST /chat`

Changing any of these routes is a breaking frontend change: update
`frontend/src/app/core/services/` in the same commit.

## Domain models — use the real fields

Pydantic v2 throughout (`pydantic>=2.0.0`; use `model_config`, `model_validator`, never `class Config`).

| Model | Defined in | Fields |
|---|---|---|
| `JobDescriptionEstructurada` | `agente_job_description/schemas/` **and duplicated** in `agente_busquedas_internas/schemas/` | keep both copies in sync — changing one alone breaks routing |
| `ResultadoRanking` | `agente_busquedas_internas/schemas/ResultadoRanking.py` | contains `candidatos_rankeados` |
| `CandidatoRankeado` | `agente_busquedas_internas/schemas/CandidatoRankeado.py` | `candidato`, `score`, `justificacion`, `habilidades_match`, `habilidades_faltantes` |
| `ShortlistReport` | `agente_busquedas_externas/src/domain/models.py` | — |
| `CandidateLead` | `agente_busquedas_externas/src/domain/models.py` | `source`, `raw_id`, `name`, `headline`, `profile_url`, `evidence` |

REJECT if a raw `dict` crosses an A2A boundary where one of these models exists.

## Models and external services

- LLMs in play: Claude (`CLAUDE_MODEL`), Gemini (`GEMINI_MODEL`), **and** OpenAI/LiteLLM
  (`agente_busquedas_externas/src/config.py`, `agente_entrevistas`). Never hardcode a model id.
- `agente_busquedas_internas` depends on RAGaaS/Qdrant MCP via `RAGAAS_MCP_URL` and collection
  settings in `agentes/config/settings.py` — a change there needs the Qdrant stack running.
- MCP over HTTP SSE (Himalayas, Tavily, Qdrant) always gets an explicit timeout and a bounded retry.
- A dead MCP source degrades the pipeline to the remaining sources; it never fails the whole request.
- Never log MCP request bodies containing candidate PII.

PREFER sequential ADK pipelines of small single-purpose sub-agents (busquedas_externas:
`IntakeAgent → JDAnalystAgent → PlannerAgent → ParallelAgent → DeduplicatorAgent → ScorerAgent →
ReportAgent`) over one large agent.

## Tool functions

ADK derives the tool schema from the signature and docstring — both are the contract.

```python
def rankear_candidatos(job_description: str, top_k: int = 5) -> ResultadoRanking:
    """Rankea candidatos internos contra una job description.

    Args:
        job_description: Texto estructurado de la posición a cubrir.
        top_k: Cantidad máxima de candidatos a devolver.

    Returns:
        ResultadoRanking con los candidatos ordenados por score descendente.
    """
```

REJECT if a tool has untyped parameters, no docstring, or a docstring that omits a parameter.

## Scoring ethics — non-negotiable

Candidate scoring is **evidence-only**, range 0–1. Only observable artifacts count: repositories,
public profiles, job titles, verifiable skills — mirrored in `CandidateLead.evidence` and
`CandidatoRankeado.justificacion`.

REJECT if:
- Score is influenced by name, gender, nationality, age, photo, or any demographic proxy
- A score is emitted without its supporting evidence/justification populated
- A heuristic infers a protected attribute from any field
