# Skill Registry

Hand-maintained. Keep in sync with the Skill Index in `AGENTS.md`.

| Name | Trigger | Description | Model |
|------|---------|-------------|-------|
| `code` | any source file | Universal standards: secrets, error handling, naming, repo layout contract | sonnet |
| `code-python` | `*.py` | Type hints, Pydantic v2, pathlib, async httpx, logging, per-agent venvs | sonnet |
| `python-adk-agents` | `agente_*/` | ADK agent anatomy, tool signatures, A2A boundaries, SSE contract, MCP clients, evidence-only scoring | sonnet |
| `agent-registry` | `agente_orchestrator/registry/` | registry.json entries, card env vars, fallback cards, port allocation | sonnet |
| `typescript-angular` | `frontend/src/**` | Angular 18 standalone + Signals, SSE cleanup and polling fallback, build output path | sonnet |
| `testing` | `tests/`, `*test*.py`, `*.spec.ts` | pytest/Angular standards, no live LLM or network calls, contract tests | sonnet |
| `commits` | git commits, PRs | Conventional commits scoped by agent, PR pre-flight checklist | sonnet |

## Commands

| Command | Purpose |
|---------|---------|
| `/review` | Skill-aware code review of a diff, branch, or working tree |
| `/status` | Git + stack health + recent memory + next priorities |
| `/sync-memory` | Write the session summary into `.harness/memory/` |
| `/handoff` | Persist unfinished work so the next session resumes cleanly |
| `/new-agent` | Scaffold and fully register a new agent end-to-end |
