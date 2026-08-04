# Memory Index

Chronological log of decisions, discoveries, conventions, and session summaries.
**Read this first at session start.** Newest entries on top.

Written by `/sync-memory` and `/handoff`. Durable topic knowledge lives in `notes/`, per-session
records in `sessions/`, spec-driven-development artifacts in `sdd/`.

Never record secrets, API keys, tokens, or candidate PII here.

## Sessions

- 2026-08-04 — [HANDOFF: Agent harness + polling endpoint](sessions/2026-08-04-handoff-agent-harness.md) — next: one manual end-to-end polling run, then push `feat/agent-harness` and open the PR
- 2026-08-04 — [Harness + polling endpoint](sessions/2026-08-04-harness-y-polling.md) — session summary: harness built, SDD cycle run, `GET /chat/status/{request_id}` implemented and hardened (30 tests, was 0)
- 2026-08-04 — [SDD verify: agent-harness](sdd/agent-harness-verify.md) — **APPROVED, 20/20 AC pass.** The audit found 12 of ~45 factual claims in the first harness draft were wrong; all corrected and now re-checkable via `python .harness/verify.py`
- 2026-08-04 — [SDD spec: agent-harness](sdd/agent-harness-spec.md) — acceptance criteria for the harness, incl. the rule that an aspirational convention presented as current reality is a FAIL
- 2026-08-04 — [Harness bootstrap](notes/harness.md) — standalone Invincible-inspired harness added (`AGENTS.md`, 7 skills, 5 commands, file-based memory)

## Notes

- [known-drift.md](notes/known-drift.md) — **verified repo defects**: `/chat/status/{request_id}` (**fixed** this session, plus the task-GC / hung-run / pending-payload leaks found in review), duplicated `JobDescriptionEstructurada`, no tests on scheduling, sync delegation path, `stop_all.sh` port mismatch, removed-but-documented legacy agents, aspirational-vs-actual Python conventions
- [harness.md](notes/harness.md) — how the harness itself is structured and extended
