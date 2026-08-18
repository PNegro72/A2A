# AGENTS.md — Coding Standards for A2A (Sistema Multi-Agente de Reclutamiento)

> **Architecture reference:** `CLAUDE.md` at the repo root describes the system topology, agents,
> ports, env vars, and run commands. Read it for *what the system is*. Read this file for *how to
> change it*.

## How to Use

When working on this project:

1. Read the **Skill Index** below
2. Identify which skill files apply to the task at hand
3. Load and follow the relevant skill file(s)
4. Multiple skills can apply simultaneously — more specific rules win over general ones
   (project extension > language > universal)

---

## Skill Index

| Trigger | Skill | Path |
|---------|-------|------|
| All source files | Universal | [`.claude/skills/code/SKILL.md`](.claude/skills/code/SKILL.md) |
| `*.py` source files | Python | [`.claude/skills/code-python/SKILL.md`](.claude/skills/code-python/SKILL.md) |
| `agente_*/` — ADK agents, A2A endpoints, tools | Python — ADK Agents | [`.claude/skills/python-adk-agents/SKILL.md`](.claude/skills/python-adk-agents/SKILL.md) |
| `agente_orchestrator/registry/`, adding an agent | Agent Registry | [`.claude/skills/agent-registry/SKILL.md`](.claude/skills/agent-registry/SKILL.md) |
| `frontend/**/*.ts`, `*.html`, `*.scss` | TypeScript — Angular | [`.claude/skills/typescript-angular/SKILL.md`](.claude/skills/typescript-angular/SKILL.md) |
| `tests/`, `*test*.py`, `*.spec.ts` | Testing | [`.claude/skills/testing/SKILL.md`](.claude/skills/testing/SKILL.md) |
| git commits, PRs | Commits | [`.claude/skills/commits/SKILL.md`](.claude/skills/commits/SKILL.md) |

---

## Session Protocol — MANDATORY

This project has **no memory CLI**. Memory is plain markdown under `.harness/memory/`.

**On session start:**
1. Read [`.harness/memory/index.md`](.harness/memory/index.md)
2. Grep `.harness/memory/` for the topic you are about to touch
3. Only then read code

**After completing any task**, append a note to `.harness/memory/` when you have:
- Made an architecture or design decision
- Found a bug and its root cause
- Discovered something non-obvious (wrong API flag, edge case, gotcha, port conflict)
- Established a convention
- Left work unfinished

Self-check after EVERY task: *"Did I learn something non-obvious or make a decision? If yes, write
it to `.harness/memory/` NOW — before the session ends."*

**Before saying "done" or ending the session:** write a session summary to
`.harness/memory/sessions/YYYY-MM-DD-<slug>.md` and add a line to `index.md`. Skipping this means
the next session starts blind.

Use `/sync-memory` to do this correctly. Use `/handoff` when work is unfinished.

**Read [`.harness/memory/notes/known-drift.md`](.harness/memory/notes/known-drift.md) before
trusting any doc in this repo.** It lists verified defects and doc/code mismatches — including a
frontend route the backend does not implement.

**If you change an orchestrator route, an agent port, or a shared schema**, run
`python .harness/verify.py`. The skills quote those values verbatim; the check fails when they drift.

### Memory file format

```markdown
---
date: 2026-08-04
type: decision | bug | discovery | convention | summary
topic: orchestrator-sse
---

# <Title>

## Context
## What happened / what was decided
## Why
## Impact on future work
```

---

## Universal Rules (all files)

REJECT if:
- Hardcoded secrets, API keys, or credentials — they belong in `.env` (never committed)
- Silent error handling (`except: pass`, empty `catch {}`)
- `TODO` / `FIXME` without a linked issue number
- Client-facing error messages that echo raw upstream response bodies or raw exception text
- A suppressed diagnostic (`# noqa`, `# type: ignore`, `@ts-ignore`, `eslint-disable`) without an
  inline comment justifying it
- New Python dependency added without updating the owning agent's `requirements.txt` or
  `pyproject.toml`

REQUIRE:
- Descriptive variable and function names
- Error messages that help debugging
- Client-facing errors surface a safe summary (HTTP status); full detail is logged server-side
- Spanish for all user-facing output and prompts. **Domain identifiers are Spanish too**
  (`rankear_candidatos`, `candidatos_rankeados`) — match the file you are editing rather than
  translating. Commit messages and registry fallback cards are English. See the `code` skill.

---

## Cross-Agent Change Checklist

A change is not complete until every applicable step is done:

1. The agent's own contract (Pydantic models) is updated on both producer and consumer sides.
   `JobDescriptionEstructurada` is **duplicated** in `agente_job_description/schemas/` and
   `agente_busquedas_internas/schemas/` — change both or neither.
2. If an agent's A2A surface changed, `registry/registry.json` **and** the matching
   `registry/fallback_cards/*.json` (`webhook_url`, `actions`, `conventions`) are updated.
3. If env vars changed, the agent's `.env.example` is updated **and** the table in `CLAUDE.md`.
4. If an orchestrator route changed, `frontend/src/app/core/services/` is updated in the same
   commit. The reverse also holds: the frontend must not reference a route the backend lacks
   (this already happened once — see the known-drift note in `.harness/memory/notes/`).
5. Focused tests for the touched agent pass (`pytest tests/ -v` inside that agent, or
   `npm test` in `frontend/`). The orchestrator and scheduling agent have **no tests** — if you
   change them, add the first one.
6. If the agent set or ports changed, `start_all.sh` and `stop_all.sh` are both updated.
7. If the orchestrator's tool signatures changed, its prompts under `agente_orchestrator/prompts/`
   are reviewed for stale instructions.
8. A memory note is written per the Session Protocol.

---

## Authoring Project-Extension Skills

Layer domain rules on top of the language skills. Naming: `<language>-<domain>/SKILL.md`.

Register **both** skills in the Skill Index so they load together:

```
| *.py source files   | Python     | .claude/skills/code-python/SKILL.md        |
| agente_*/           | ADK Agents | .claude/skills/python-adk-agents/SKILL.md  |
```

Skeleton:

```yaml
---
name: python-<domain>
description: "One line: what this covers and when it applies."
when_to_use: "Concrete trigger conditions."
user-invocable: false
model: sonnet
---

# Skill: Python — <Domain>

## Rules

REJECT if:
REQUIRE:
PREFER:
```

---

## Engineering Persona

- Zero pleasantries. No "Here is the code" or "Let me know if you need anything else."
- Token minimalism. Deliver the exact insight or code needed. No filler.
- Radical candor. If an approach is stupid, overcomplicated, or insecure — say so and dictate the
  pragmatic alternative.
- Verify technical claims before stating them. If unsure, investigate first.
- If wrong, acknowledge with proof. If the user is wrong, explain WHY with evidence.
- Talk is cheap. Show the code.
- Good programmers worry about data structures and state; bad programmers worry about abstract
  design patterns.
- Strict adherence to DRY, KISS, YAGNI, and OWASP. Ruthlessly eliminate over-engineering.
- AI IS A TOOL: we direct, AI executes; the human always leads.
