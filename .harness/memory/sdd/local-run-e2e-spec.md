---
date: 2026-08-05
type: spec
change_id: local-run-e2e
topic: local-setup
---

# SDD Spec: local-run-e2e

## Goals

Get the full SAPE system (6 agents + MCP + Qdrant RAG backend + frontend) running locally on a
fresh Windows machine with real credentials, and prove — with real, reproducible evidence, not
assumptions — that every chat-reachable capability actually works end-to-end against the live
stack: real LLM calls, real external APIs, real indexed data, real generated artifacts.

## Non-Goals

- Building new product features. Every code change in this cycle exists to unblock or fix
  something the setup/testing work surfaced — nothing was added speculatively.
- Setting up real Google Calendar OAuth (out of the user's reach in-session); scheduling is
  explicitly mocked instead (`SCHEDULING_MOCK=true`, `calendar_service_mock.py`), with the real
  path left intact and switchable back with one env var.
- Fixing every issue found. The deduplicator JSON-truncation bug in `busquedas_externas` is
  documented as an open follow-up, not fixed — an attempted fix (`parallel_tool_calls=False`)
  was tried, measured, found ineffective, and reverted rather than left as a false claim.
- Committing any of this work. All changes are local, uncommitted, on `feat/agent-harness`.

## Acceptance Criteria

### Setup / structural

- [ ] **AC-1** Every one of the 7 Python components (`agente_orchestrator`,
      `agente_job_description`, `agente_busquedas_internas`, `agente_entrevistas`,
      `agente_scheduling`, `agente_busquedas_externas`, `MCP`, `Qdrant` — 8 total) has a `.venv`
      with every runtime dependency actually importable, including ones lazily imported inside
      functions (not caught by a top-level smoke import).
- [ ] **AC-2** `./start_all.sh` boots all 8 backend services **and** the frontend unattended,
      reports every service `listo`, and exits 0 — no manual per-service restarts required.
- [ ] **AC-3** `./stop_all.sh` actually terminates every process it claims to stop (it did not,
      before this cycle — see Verify).
- [ ] **AC-4** Every `.env` used by a running service contains every variable that service's code
      fail-fasts on (`os.environ[...]`, `require_env(...)`, pydantic `Field(...)` with no
      default) — including variables missing from `.env.example` itself.
- [ ] **AC-5** `OPENAI_API_KEY`, `GITHUB_TOKEN`, `TAVILY_API_KEY`, `QDRANT_URL`+`QDRANT_API_KEY`
      are real, live credentials, each verified against the real service they authenticate to —
      not placeholders that merely satisfy a presence check.

### Behavioural — each claim below is a real chat round-trip, not a unit test

- [ ] **AC-6** `POST /chat` → orchestrator calls the OpenAI-backed LLM and returns a real
      generated response (not a stub, not an error swallowed into a generic message).
- [ ] **AC-7** Internal candidate search (`busquedas_internas`) returns ranked candidates sourced
      from real indexed CV data (not an empty or mocked result).
- [ ] **AC-8** External candidate search (`busquedas_externas`) returns real sourced candidates
      from live Himalayas/GitHub calls, with evidence-based scoring and honest gap-flagging.
- [ ] **AC-9** Interview kit generation (`entrevistas`) produces a real, valid, downloadable
      `.docx` for a candidate found via **either** internal or external search in the same
      conversation turn as a combined search (not just for a candidate from a single-source
      search — this distinction is exactly what the interview-prep bug below hid).
- [ ] **AC-10** Scheduling (mocked) proposes a slot and reaches the confirmation step through
      natural-language chat, including ordinal reference resolution ("el primero").
- [ ] **AC-11** JD drafting from a short request (`redactar_jd`) is reachable from chat, not just
      from a direct HTTP call to the agent.
- [ ] **AC-12** A CV file attached in `/chat` has its text actually extracted (PDF or Word) and
      used by the LLM in its response — not silently dropped.
- [ ] **AC-13** The orchestrator responds in Spanish regardless of the input language.
- [ ] **AC-14** An off-topic / unsupported request gets an honest "no agent available" answer,
      never a forced delegation to a mismatched agent.
- [ ] **AC-15** At least one full flow is exercised by the user through the actual rendered UI in
      a real browser, unscripted — not only through my own scripted API calls.

## Constraints

- No fabricated or placeholder credentials presented as working. Every "done" claim for a
  credentialed integration is backed by a live call against the real service.
- No secrets echoed back into chat responses or logs beyond what's needed to write them into
  `.env` files (which stay `.gitignore`d).
- Code comments added to existing files match the file's own existing language convention
  (Spanish for the agent codebases) — not a blanket English default.
- Any fix attempted must be verified by reproducing the original failure and confirming it no
  longer occurs — not assumed correct because it looks right.
- An attempted fix that does not measurably work must be reverted, not left in place with a
  comment claiming success.

## Added during the cycle

- [ ] **AC-16** `stop_all.sh`'s port list includes every port `start_all.sh` actually starts
      (8007 for the Qdrant backend was missing).
- [ ] **AC-17** The `busquedas_internas` interview-prep prompt path checks **both** the internal
      and external candidate shortlists from conversation history, not external-only (the bug
      the user caught live in the UI).

## Out of Scope

- Fixing the deduplicator JSON-truncation issue in `busquedas_externas` (documented, not fixed).
- Real Google Calendar OAuth setup.
- Any change to agent business logic beyond what's needed to make an existing, advertised
  capability actually reachable or actually correct.
