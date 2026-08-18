---
date: 2026-08-04
type: session
topic: harness-y-polling
---

# Session — Agent harness + `GET /chat/status/{request_id}`

## What was asked

An Invincible-inspired AI agent harness for this repo, explicitly **without** making it an
Invincible-managed repository and without depending on the `invincible` CLI. Then: "100% sure? can
we run an SDD cycle to make sure?" — which is what turned a documentation exercise into a bug fix.

## What was built

**Harness (standalone, no external tooling):** `AGENTS.md` as the entry point, 7 skills under
`.claude/skills/`, 5 slash commands under `.claude/commands/`, and `.harness/` holding config, the
skill registry, and file-based memory. The `invincible memory save` CLI is replaced by plain
markdown files plus `/sync-memory`.

The judgement call worth remembering: the value in Invincible is the **convention**, not the
tooling. Markdown-only gets ~90% of the benefit at ~0 maintenance and cannot break the build. Hooks,
the SDD skill chain, wiki sync, dual-model review, and the memory daemon were deliberately omitted.

**SDD cycle.** `.harness/memory/sdd/agent-harness-spec.md` defines 17 binary acceptance criteria,
including AC-13: *an aspirational convention presented as current reality is a FAIL*. An audit agent
verified ~45 factual claims from the first draft against the actual code. **12 were wrong.** All 7
skills were rewritten against measured reality, and `CLAUDE.md` was corrected — it documented a
legacy healthcare demo (ports 9997–9999) that does not exist in the tree.

`.harness/verify.py` (stdlib only, 20 checks) makes the criteria re-runnable. Writing it violated
the spec's own "markdown only" constraint, so the constraint was amended in the spec rather than the
violation being left unmentioned.

## The bug the SDD cycle found

`environment.transportMode` accepted `'polling'` and `config.service.ts` built a URL for
`GET /chat/status/{request_id}`, but the orchestrator never implemented that route. Polling mode was
simply broken.

Implemented it by extracting the ADK event loop into one generator, `_run_agent_events()`, feeding
both SSE and polling, with state in a new ADK-free `request_state.py`. No frontend change was
needed — the existing `PollingResponse` shape already matched.

An independent review then caught three liveness/memory defects in that first cut, all fixed:

1. `asyncio.create_task()` with no stored reference — the loop keeps only a weak reference, so a run
   could be garbage-collected mid-execution.
2. A hung run left the client polling forever and its state permanently unpurgeable. Unlike SSE,
   polling has no client disconnect to cancel anything. Now bounded by `RUN_TIMEOUT_SECONDS`, and
   `purge_expired` also drops states stuck in `running`.
3. `pending_requests` was never purged, retaining base64 CVs for the process lifetime.

## Constraints discovered (now in the skills)

- **A `request_id` is consumed by whichever transport claims it first.** So an automatic SSE→polling
  `catchError` failover cannot work — the retry would 404. Failover needs a fresh `request_id`.
- A run ending without a final response must terminate as `NO_FINAL_RESPONSE`, or the client's
  `takeWhile` polls forever.
- `server.py` imports ADK at module load, so tests need `sys.modules` stubs in `conftest.py`. Better
  pattern: keep new logic in ADK-free modules.

## State

`python .harness/verify.py` → 20/20. `pytest tests/ -q` in `agente_orchestrator` → 30/30 (the
orchestrator had zero tests before this session). Committed as two commits on `feat/agent-harness`,
branched from `main` @ `8ff070c`; not pushed. See the handoff note for how to resume.

Not validated: no live end-to-end run against a real orchestrator + LLM — tests use a stubbed ADK
runner. `agente_scheduling` still has no tests.
