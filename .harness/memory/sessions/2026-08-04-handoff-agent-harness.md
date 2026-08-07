---
date: 2026-08-04
type: handoff
topic: agent-harness
---

# HANDOFF — Agent harness + polling endpoint

- `change_id`: agent-harness
- `last_completed_step`: Both commits made on `feat/agent-harness`; harness verify 20/20 and orchestrator tests 30/30 re-run against the committed state
- `current_state`: Branch `feat/agent-harness` exists locally with two commits on top of `main` @ `8ff070c`, working tree clean, nothing pushed and no PR opened. The harness (AGENTS.md, 7 skills, 5 commands, `.harness/`) is complete and self-verifying. `GET /chat/status/{request_id}` is implemented and hardened, but has **never been exercised against a real orchestrator + LLM** — all 30 tests use a stubbed ADK runner.
- `next_step`: Do one manual end-to-end run of polling mode (start the orchestrator, set `environment.transportMode = 'polling'`, send a message through the frontend) before pushing or merging.

## 1. What was accomplished

Built a standalone Invincible-inspired harness — deliberately *not* an Invincible-managed repo, no
dependency on that CLI. The SDD cycle run over it found 12 of ~45 factual claims in the first draft
were wrong, including a live production bug: the frontend's polling transport pointed at a route the
orchestrator never implemented. That route is now implemented, and an independent review of the
first cut caught three further defects (task GC, hung-run liveness, retained base64 CV payloads),
all fixed and covered by tests.

## 2. Current state

```
feat/agent-harness
  b0ae432 chore(harness): add standalone agent harness with skills, commands and memory
  29b9174 feat(orchestrator): implement GET /chat/status/{request_id} polling transport
  8ff070c (main, origin/main) Merge pull request #6 ...
```

- Working tree clean; `main` untouched and still in sync with `origin/main`.
- **Not pushed, no PR.**
- No process left running. `agente_orchestrator/.venv/` exists locally (gitignored) and holds
  `pytest fastapi httpx opentelemetry-api python-dotenv uvicorn`. `google-adk` is **not** installed
  there — it is stubbed in `tests/conftest.py`.

## 3. Known issues / blockers

No errors outstanding. Two honest gaps:

- **No live validation.** The wiring is verified, the real ADK + LLM path is not. This is the only
  reason the work is not ready to merge.
- Pre-existing, untouched: `agente_scheduling` has no tests; `JobDescriptionEstructurada` is
  duplicated in two agents with no test asserting the copies agree; `stop_all.sh` lists port 8006 in
  one place and omits it in its fallback loop, and no agent owns 8006.

## 4. Next steps, ordered

1. Manual end-to-end polling run (see `next_step`). Watch for: steps arriving cumulatively, the
   stream terminating on `done`, and no request left `running`.
2. `git push -u origin feat/agent-harness` and open the PR.
3. Decide whether `.harness/verify.py` belongs in CI, or stays a manual check.
4. Optional follow-ups from the verify doc: a test asserting the two `JobDescriptionEstructurada`
   copies agree; a first test for `agente_scheduling`; reconcile the `stop_all.sh` port list.

## 5. Relevant files

| File | What's in play |
|---|---|
| `agente_orchestrator/server.py` | `_run_agent_events()` is the single event source for both transports; `chat_status()` starts the run on first poll; `_accumulate_events()` wraps it in `asyncio.wait_for(RUN_TIMEOUT_SECONDS)`; `_take_pending()` / `_purge_pending()` |
| `agente_orchestrator/request_state.py` | `RequestStateStore`; `purge_expired()` now also drops states stuck in `running` past `max_running_seconds` |
| `agente_orchestrator/tests/conftest.py` | `sys.modules` stubs for `google.adk` etc., installed before `server.py` is imported |
| `frontend/src/app/core/services/orchestrator.service.ts` | `pollStatus()` — consumer of the new route, unchanged, verified compatible |
| `.harness/memory/notes/known-drift.md` | The verified defect list; items 1 and 1b are the ones closed today |

## 6. How to re-verify

```powershell
cd C:\Users\juan.daza\aitribe\A2A
git checkout feat/agent-harness
python .harness\verify.py                                    # expect 20/20 PASS
cd agente_orchestrator
.\.venv\Scripts\python.exe -m pytest tests/ -q               # expect 30 passed
```

## Design constraints worth not re-deriving tomorrow

- A `request_id` is consumed by whichever transport claims it first, so an automatic SSE→polling
  `catchError` failover **cannot** work — the retry would 404. Failover needs a fresh `request_id`.
- Polling has no client disconnect, so nothing cancels an abandoned run. That is why the timeout and
  the `running`-state purge exist; do not remove them as "defensive".
- `asyncio.create_task()` results must be held in `_background_tasks` — the loop keeps only weak
  references.
