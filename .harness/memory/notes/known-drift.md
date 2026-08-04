---
date: 2026-08-04
type: discovery
topic: known-drift
---

# Known Drift — Verified Inconsistencies in the Repo

Found while auditing harness claims against the codebase (2026-08-04). These are **real defects or
inconsistencies in the project**, not harness problems. Each one is documented in the relevant skill
so agents stop propagating the wrong assumption.

## 1. Frontend polling transport points at a non-existent route — **FIXED 2026-08-04**

`frontend/src/app/core/services/config.service.ts` built a status URL for
`/chat/status/{request_id}`, and `environment.transportMode` accepted `'polling'`, but the
orchestrator never implemented the route — setting polling mode broke the UI.

**Resolved by implementing `GET /chat/status/{request_id}`.** The ADK event loop was extracted into
a single generator, `_run_agent_events()`, feeding both SSE and polling; polling state lives in the
new ADK-free `agente_orchestrator/request_state.py`. No frontend change was needed — the response
shape already matched the client's `PollingResponse`.

Two constraints that came out of it, now recorded in the skills:

- A `request_id` is consumed by whichever transport claims it first, so an automatic SSE→polling
  `catchError` failover cannot work — the retry would 404. Failover requires a new `request_id`.
- A run that ends without a final response now terminates as `NO_FINAL_RESPONSE` instead of leaving
  `status: running`, which would have made the client poll forever.

Also fixed in passing: the shared error path no longer returns `str(exc)` to the client (it leaked
internals); the detail is logged and a generic message is returned.

Follow-up review (2026-08-04) caught two liveness/memory gaps in the first cut of this endpoint,
both now fixed and covered by tests:

- The background task was passed to `asyncio.create_task()` without keeping a reference. The event
  loop only holds weak references, so a run could be garbage-collected mid-execution. It is now
  held in `_background_tasks` and discarded via `add_done_callback`.
- A hung run left the client polling forever (unlike SSE, no client disconnect cancels it) and its
  state was unpurgeable, because `purge_expired` only considered *finished* states. The run is now
  bounded by `RUN_TIMEOUT_SECONDS` (surfaced as `RUN_TIMEOUT`), and `purge_expired` also drops
  states stuck in `running` past `max_running_seconds`.

## 1b. `pending_requests` retained abandoned CV payloads — **FIXED 2026-08-04**

Entries were only ever removed by whichever transport claimed them. Any `POST /chat` that was never
followed by a stream or poll (tab closed, proxy blocking SSE, network drop) left the entry — and its
base64 file, i.e. a whole CV — resident for the lifetime of the process. Now purged on `POST /chat`
via `_purge_pending()`, governed by `PENDING_TTL_SECONDS`.

## 2. `JobDescriptionEstructurada` is duplicated

Defined independently in `agente_job_description/schemas/` and
`agente_busquedas_internas/schemas/`. There is no shared package and no test asserting the two
copies agree, so they can silently diverge and break JD → ranking routing.

## 3. `stop_all.sh` port list is internally inconsistent

Line 10 lists `8000 8001 8002 8003 8004 8006 8080 4200`; the `lsof` fallback loop at line 25 omits
`8006`. Port `8006` is not assigned to any agent. The scripts also assume Git Bash on Windows
(`/tmp/sape_logs`, `lsof`).

## 4. CLAUDE.md documented components that do not exist

It described a legacy healthcare A2A demo — `a2a_policy_agent.py`, `a2a_provider_agent.py`,
`a2a_research_agent.py`, `mcpserver.py`, `data/doctors.json`, ports 9997–9999. **None are present in
the tree.** Removed from `CLAUDE.md`. `GOOGLE_APPLICATION_CREDENTIALS` was documented as belonging
to those agents and is now effectively unused.

## 5. Scheduling agent has zero tests — orchestrator now covered

`agente_scheduling` still has no `tests/` directory.

`agente_orchestrator` had none either until 2026-08-04; it now has 30 tests (`pytest.ini`,
`tests/`). The blocker was that `server.py` imports ADK at module load — solved with `sys.modules`
stubs in `tests/conftest.py`, plus keeping new logic in the ADK-free `request_state.py`.

## 5b. Orchestrator manifest was incomplete

`requirements.txt` did not list `fastapi` or `uvicorn` even though `server.py` imports both
directly (they came in transitively via `google-adk`). `.env.example` omitted `CORS_ALLOWED_ORIGINS`
and `LOG_LEVEL`, both read as `os.environ[...]` at import — a fresh clone failed to boot. Both
fixed.

## 6. Delegation path is synchronous

`call_external_agent(agent_name: str, payload: dict) -> dict` uses `requests.post(...)`, not
`httpx.AsyncClient`. It is load-bearing and untested — do not convert it to async as a side effect
of an unrelated change.

## 7. Stated conventions were largely aspirational

Measured across 110 `.py` files: `from __future__ import annotations` 3.6%, `pathlib` 10%,
`logging` 17.3% (with `print()` at 8.2%). Commit history: ~31% conventional, ~23% scoped, several
`cambios` / `tu mensaje`. Identifiers and comments are frequently Spanish. The skills now label
these as *target conventions to converge on*, with the current prevalence stated, rather than
pretending they are the existing norm.
