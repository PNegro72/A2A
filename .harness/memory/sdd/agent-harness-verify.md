---
date: 2026-08-04
type: verify
change_id: agent-harness
topic: harness
---

# SDD Verify: agent-harness

Verdict produced by re-checking every acceptance criterion in `agent-harness-spec.md` after the
correction pass. Mechanical checks are reproducible with `python .harness/verify.py`.

## Acceptance criteria

| Criterion | Status | Evidence |
|---|---|---|
| AC-1 AGENTS.md tracked-able | PASS | `git check-ignore AGENTS.md` rc=1 after removing it from `.gitignore` |
| AC-2 skill index resolves | PASS | 7 indexed, 0 missing |
| AC-3 frontmatter name == dir | PASS | 7 skills, 0 mismatches |
| AC-4 commands ↔ registry bidirectional | PASS | both = handoff, new-agent, review, status, sync-memory |
| AC-5 relative links resolve | PASS | 0 broken across 5 docs |
| AC-6 registry set == index set | PASS | 7 == 7 |
| AC-7 no harness file ignored | PASS | 27 files checked, 0 ignored |
| AC-8 agent layout claims true | PASS *(after fix)* | Replaced the false "every agent has `agentes/<name>/agent.py`, `prompts/`, `tools/`, `tests/`" with a per-agent table; all 6 dirs listed; uniformity explicitly disclaimed |
| AC-9 endpoints match reality | PASS *(after fix)* | Real routes: `/chat`, `/chat/stream/{request_id}`, `/health`. `/chat/status/{request_id}` was claimed as a working fallback — it does not exist; now documented as open drift |
| AC-10 referenced paths exist | PASS *(after fix)* | 17 referenced repo paths, all exist; ghost legacy files removed |
| AC-11 ports match code | PASS *(after fix)* | 8000/8001/8002/8003/8004/8080 cross-checked against each `.env.example`; invented 9997–9999 removed |
| AC-12 model fields real | PASS *(after fix)* | `CandidatoRankeado` example used invented `nombre`/`evidencia`; corrected to `candidato`, `score`, `justificacion`, `habilidades_match`, `habilidades_faltantes`. `CandidateLead` corrected to `source`, `raw_id`, `name`, `headline`, `profile_url`, `evidence` |
| AC-12b delegation signature verbatim | PASS *(after fix)* | Claimed `httpx.AsyncClient`; reality is sync `requests.post` with `AGENT_HTTP_TIMEOUT`. Signature now quoted from source |
| AC-13 aspirational rules labelled | PASS *(after fix)* | `code-python` now splits "Enforced now" from "Target convention" with measured prevalence (`__future__` 3.6%, pathlib 10%, logging 17.3%) |
| AC-14 commit convention honest | PASS *(after fix)* | Declared a **new** convention; cites ~31% conventional / ~23% scoped in last 35 commits |
| AC-15 unambiguous skill routing | PASS | Trigger→path table, 7 rows |
| AC-16 protocol needs no tooling | PASS | Start: `.harness/memory/index.md`; end: `/sync-memory` |
| AC-17 AGENTS.md ↔ CLAUDE.md | PASS | Bidirectional links; contradictions in `CLAUDE.md` corrected |
| AC-18 verifier green | PASS | `python .harness/verify.py` → 20/20 PASS, exit 0 |

## Regression check

Not applicable in the usual sense — no agent source, test, or build config was modified. Confirmed
by `git status`: changes are confined to `AGENTS.md`, `.claude/`, `.harness/`, `.gitignore`, and
factual corrections to `CLAUDE.md`.

## What the cycle actually caught

The first pass was **12 of ~45 factual claims wrong** — roughly a quarter. Not typos: the harness
asserted an agent layout that no agent fully matches, an HTTP client the code does not use, model
fields that do not exist, an endpoint that is not implemented, and four "existing conventions" that
were really my preferences at 3–17% adoption. Shipping that would have made every future agent
confidently wrong.

It also surfaced 7 genuine repo issues, recorded in `.harness/memory/notes/known-drift.md` — the
`/chat/status` gap is a live frontend bug.

## Verdict

**APPROVED.** 20/20 acceptance criteria pass, mechanically re-checkable.

## Follow-ups (not blocking, not harness work)

1. Fix the `/chat/status/{request_id}` gap — implement the route or delete the polling transport.
2. Add a test asserting the two `JobDescriptionEstructurada` copies agree.
3. First test for `agente_orchestrator` and `agente_scheduling`.
4. Reconcile the `stop_all.sh` port list with its fallback loop; clarify port 8006.
