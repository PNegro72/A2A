---
date: 2026-08-05
type: verify
change_id: local-run-e2e
topic: local-setup
---

# SDD Verify: local-run-e2e

Verdict produced by re-checking every acceptance criterion in `local-run-e2e-spec.md`, including a
mid-cycle merge with `origin/main` (PR #7, `fix/agente_entrevistas`) that required re-verifying
several already-passed criteria.

## Acceptance criteria

| Criterion | Status | Evidence |
|---|---|---|
| AC-1 all 8 venvs fully importable | PASS *(after fixes)* | `google-adk[extensions]` missing for orchestrator/job_description/busquedas_internas (LiteLlm import); `mcp>=1.2.0` unbounded pulled 2.0.0 which removed `FastMCP`/`streamablehttp_client` (pinned `<2.0.0` in `MCP/` and `agente_busquedas_internas/`); `python-pptx` missing from `Qdrant/requirements.txt` despite being a declared `SUPPORTED_EXTENSIONS` loader; `pymupdf`/`python-docx` missing from orchestrator venv despite `_extraer_texto_base64` needing them (degraded silently, never crashed, never worked) |
| AC-2 `start_all.sh` boots everything unattended | PASS *(after fixes)* | Two independent bugs: `@PY@` placeholder never used in `AGENTS` array commands (hardcoded `.venv/bin/python`, wrong on Windows); missing `probe` field on original 4-field entries caused literal-string bug where `probe_ok()` received garbage. Also added `qdrant_backend`/`mcp_server` entries (script's own comments claimed it started them; it didn't) |
| AC-3 `stop_all.sh` actually stops everything | PASS *(after fix)* | Original read only 3 of 4 colon-separated PID-file fields, so `pid` became `"12345:health"` — `kill -0` silently failed on every entry, nothing ever got killed. Rewrote to kill by port via `netstat`+`taskkill`, matching `start_all.sh`'s own working pattern |
| AC-4 every fail-fast env var present in `.env` | PASS *(after fixes)* | `agente_orchestrator/.env.example` never listed `CLAUDE_API_KEY`/`CLAUDE_MODEL` despite `main.py` requiring them; `agente_job_description` and `agente_busquedas_internas` `.env.example` never listed the Claude vars their own `Settings` class required either (all three: switched off Anthropic to OpenAI instead, per user decision — see AC-9); `Qdrant/.env.example` missing `OPENAI_API_KEY` despite `config.py` requiring it; `Qdrant/.env.example`'s `DENSE_MODEL`/`DENSE_VECTOR_SIZE` defaults (`all-MiniLM-L6-v2`/384) didn't match the actually-active OpenAI embedding path (`text-embedding-3-small`/1536) |
| AC-5 real credentials, live-verified | PASS | `OPENAI_API_KEY`: real chat completions via `gpt-5.6-terra` confirmed. `GITHUB_TOKEN`: `GET /rate_limit` returned 5000/hr authenticated limit. `TAVILY_API_KEY`: wired into busquedas_externas, used in a real sourcing run. `QDRANT_URL`+`QDRANT_API_KEY`: real Cloud cluster, 38 real CVs ingested (306 chunks), real search results returned end-to-end through MCP |
| AC-6 real chat round-trip | PASS | `POST /chat` → real `gpt-5.6-terra` response, non-error, verified multiple times across the session |
| AC-7 internal search returns real ranked results | PASS | Verified pre- and post-merge; real candidates from the 38 ingested CVs, real scores/gaps |
| AC-8 external search returns real sourced results | PASS | Verified pre- and post-merge; real Himalayas/GitHub profiles, evidence-based scoring, honest gap-flagging |
| AC-9 interview kit works for a candidate found via either source in a combined-search turn | PASS *(after two rounds of fixes)* | Round 1: orchestrator prompt only searched the *external* shortlist when preparing an interview — an internal-only candidate found alongside external results in the same turn was reported "not found." Fixed pre-merge. Round 2: the upstream merge (PR #7) rewrote this flow generically ("candidate profile data") without shortlist lookup at all — regressed to not finding *either* source's data (asked for an email that was already in the internal ATS profile). Re-added an explicit "Step 0" candidate-lookup instruction covering both shapes; reverified live with the exact full name (works) and a shortened name (LLM fuzzy-match miss — a soft, pre-existing characteristic, not a regression) |
| AC-10 scheduling (mocked) reaches confirmation via ordinal reference | PASS | Verified pre-merge (full flow) and post-merge (propose step); the merge removed the dedicated "Scheduling flow" prompt section entirely — reverified and found generic delegation + the agent card's own conventions were sufficient, no fix needed |
| AC-11 `redactar_jd` reachable from chat | PASS *(after fix)* | The working `POST /a2a/redactar_jd` endpoint was never advertised in the orchestrator's agent card for `job_description_agent` (which only listed `parsear_jd`) — the orchestrator had no way to know the capability existed. Added the missing card entry; verified via chat |
| AC-12 CV attachment text extraction used by the LLM | PASS *(after fix, see AC-1)* | Once `pymupdf`/`python-docx` were installed, a test `.docx` CV's extracted text was correctly used by the LLM (it named the candidate from the CV verbatim in its response) |
| AC-13 responds in Spanish regardless of input language | PASS | English input ("I need a backend developer with Go experience...") answered fully in Spanish |
| AC-14 off-topic requests get honest refusal | PASS | "¿Qué clima hace hoy en Buenos Aires?" → "No cuento con un agente disponible..." — no forced delegation |
| AC-15 real UI test, unscripted | PASS | User ran `./start_all.sh` in their own terminal and drove the chat UI directly in a browser — combined internal+external search in one turn (a scenario not in my own scripted sweep), correct evidence-based results, correct gap-flagging |
| AC-16 `stop_all.sh` port list matches `start_all.sh` | PASS | Rewritten port list includes 8007 (Qdrant backend) |
| AC-17 interview-prep checks both shortlists (harness's own added criterion) | PASS *(after two rounds — see AC-9)* | Same evidence as AC-9 |

## Regression check

Working tree carries only local, uncommitted-until-now changes plus one real merge commit
(`c0ddf6d`, merging `origin/main`'s PR #7). The merge itself required manual conflict resolution in
`agente_orchestrator/server.py` (kept the polling-transport refactor's shared `_run_agent_events()`
helper, added `files` multi-CV support inside it rather than reintroducing upstream's duplicated
inline SSE logic) and in five files where both sides made the *same* fix independently
(`max_tokens`→`max_completion_tokens` ×3, `reasoning_effort="none"` ×2) — those resolved to
zero-diff-from-upstream once reconciled. `prompts/orchestrator.py` was taken from upstream wholesale
per explicit user decision, then had two regressions patched back in (see AC-9, AC-17) as small,
targeted additions — not a revert of upstream's new CV-ranking feature, which is untouched and not
independently tested in this cycle (out of scope — see spec's Non-Goals).

## What the cycle actually caught

Eleven real, independent bugs across dependency pinning, agent-card completeness, `.env.example`
completeness, two shell-script logic bugs (`start_all.sh`'s dead `@PY@` substitution and field-count
bug; `stop_all.sh`'s field-count bug that silently no-op'd every kill), an embedding-model/dimension
mismatch, and — found only by the user driving the real UI, not by any scripted test — a prompt
bug where multi-source search results silently made half the results unreachable for follow-up
actions. That last one recurred in a different shape after an upstream merge rewrote the same
prompt section, which is the clearest evidence in this cycle that "generically worded, no explicit
data-lookup instruction" is a recurring failure mode for this LLM, not a one-off.

One issue was investigated and explicitly **not** fixed: `busquedas_externas`'s deduplicator drops
some candidates when the model truncates a long `save_candidate` tool-call argument. Tried
`parallel_tool_calls=False` on the hypothesis that parallel calls were interfering — measured,
found no improvement, reverted. Documented as an open, unresolved issue rather than left as a false
"fixed" claim.

## Verdict

**APPROVED**, with one documented open issue (deduplicator truncation) and one explicit scope
boundary (real Google Calendar OAuth not set up — scheduling runs on `SCHEDULING_MOCK=true` against
`calendar_service_mock.py`, same interface as the real path, switchable back with one env var).

## Follow-ups (not blocking, not in this cycle's scope)

1. Fix the `busquedas_externas` deduplicator JSON-truncation issue — likely needs the tool
   restructured to take smaller arguments, or leads merged in Python instead of via LLM-reconstructed
   JSON, rather than another prompt-level or API-parameter-level workaround.
2. Set up real Google Calendar OAuth (`credentials.json` via a Desktop-app OAuth client) and flip
   `SCHEDULING_MOCK=false` when ready.
3. The upstream `CV Ranking flow` (multi-CV upload → `rankear_candidatos`) is untested in this cycle
   — worth a dedicated pass.
4. Cosmetic: a `"message": "null"` (literal string) appears in one internal step trace under load;
   not user-visible (steps aren't rendered in the chat UI), low priority.
