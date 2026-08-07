---
date: 2026-08-07
type: summary
topic: local-setup
---

# Session summary — 2026-08-07: re-verify local run + open PR

## Context

User has a demo in ~2h and asked to run + fully test the stack and open a PR to `main` for all
`feat/agent-harness` work. Continues the 2026-08-05 `local-run-e2e` cycle (APPROVED); the only
pending step per the 2026-08-04 handoff was one live polling run, then push + open the PR.

## What was done

- Booted the whole stack with `./start_all.sh`: all 8 backends + frontend reported `listo`, all
  9 ports listening (8000-8004, 8006, 8007, 8080, 4200), and the daemons persisted after the
  launcher process exited.
- **First live validation of the polling transport against the real orchestrator + LLM** (the
  2026-08-04 handoff's open gap): `POST /chat` (English input) → polled `GET /chat/status/{id}`
  → status running→done, real Spanish response returned. Confirms AC-6 + AC-13 live, and that
  the polling path works end-to-end (previously only covered by stubbed-runner tests).
- Unit suites: orchestrator 30/30, busquedas_internas 15/15, job_description 13/13,
  entrevistas 66/66 (after fix), busquedas_externas 43 pass / 4 fail (pre-existing — see below).
- Fixed `agente_entrevistas/tests/test_generar_preguntas.py`: still mocked the Anthropic client
  shape (`messages.create` / `content[0].text`) after the cycle switched `generar_preguntas` to
  OpenAI; updated to the OpenAI shape (`chat.completions.create` / `choices[0].message.content`).
  5 red → green.
- Committed the local-run-e2e cycle (excluding `Qdrant/cache/*.db*`, `.claude/settings.local.json`,
  and — per user decision — the scheduling mock, kept LOCAL-ONLY), pushed `feat/agent-harness`,
  opened **PR #8** to `main`: https://github.com/PNegro72/A2A/pull/8
- Later removed the scheduling mock from the already-pushed branch by rewriting the two e2e commits
  (code + docs) and force-pushing with `--force-with-lease` (safety backup at local branch
  `backup-with-mock`). The mock still works locally for the demo.

## Non-obvious findings

- `busquedas_externas`'s 4 unit failures are PRE-EXISTING, not this branch's regression: its test
  files and `src/models.py` are byte-identical to `origin/main`. Three are model-validation tests;
  one asserts `Bearer None` but the real `.env` `GITHUB_TOKEN` bleeds into the unmocked test env.
- `python .harness/verify.py` now reports 19/20: AC-7 FAILs only because it recurses into
  `frontend/node_modules` and finds `.claude/` test fixtures inside the third-party `resolve`
  package. False positive that appears only when `node_modules` is installed — verify.py should
  skip `node_modules`. Not fixed this session.
- `gh` CLI is not installed on this machine; the git credential manager already has push auth.
  PR opened via the GitHub compare URL rather than `gh pr create`.
- The `agente_entrevistas` venv lacked `pytest` (its `requirements.txt` omits it) — installed it
  to run the suite. Worth adding as a dev dependency.

## Demo caveats to communicate

- Scheduling runs on `SCHEDULING_MOCK=true` — it does NOT touch real Google Calendar. The mock
  (`calendar_service_mock.py` + the `SCHEDULING_MOCK` switch in `server.py`) is deliberately kept
  LOCAL-ONLY and is NOT committed: `calendar_service_mock.py` is listed in `.git/info/exclude`, and
  the `server.py` switch is protected with `git update-index --skip-worktree agente_scheduling/server.py`.
  Real Google Calendar OAuth (someone else holds the credentials) is the follow-up; when wired up,
  drop the local mock (`--no-skip-worktree` on server.py, delete the mock file + exclude line).
- `busquedas_externas`'s deduplicator can still drop some candidates when the model truncates a
  long `save_candidate` tool-call argument (documented open issue, not fixed).

## Impact on future work

- One-line verify.py fix to skip `node_modules` (and probably `.venv`) during the AC-7 scan.
- Add `pytest` to `agente_entrevistas` dev deps; consider a CI gate running all suites.
- The 3 pre-existing `busquedas_externas` model tests and the env-bleed test deserve a cleanup pass.
