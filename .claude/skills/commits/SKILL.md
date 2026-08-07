---
name: commits
description: "Commit message format, branch naming, and PR preparation rules for this repo. New convention as of 2026-08 — existing history is mixed. Use when creating a commit, opening a PR, or cleaning up a branch."
when_to_use: "Any git commit, branch, or pull request work."
user-invocable: false
model: sonnet
---

# Skill: Commits

## Status of this convention

**This is a new convention adopted 2026-08.** Measured history is mixed: of the last 35 commits,
~31% were conventional-ish and only ~23% carried a scope; several are `cambios`, `Cambios`, or
`tu mensaje`. Do not use existing history as a style reference, and do not rewrite it — apply the
rules below going forward.

## Format

```
<type>(<scope>): <description>
```

Types: `feat`, `fix`, `refactor`, `docs`, `test`, `chore`, `perf`.
Scopes: `orchestrator`, `job-description`, `busquedas-internas`, `busquedas-externas`,
`entrevistas`, `scheduling`, `frontend`, `mcp`, `qdrant`, `harness`.

Good precedent from real history: `feat(scheduling): treat participants as invitees with the
organizer implicit`.

Branches: `feat/<slug>`, `fix/<slug>` (matches `feat/agente-n8n`,
`feat/connection-with-rag` already in the repo).

## Rules

REQUIRE:
- Imperative mood: "add", not "added" / "se agrega"
- Subject ≤ 72 characters, no trailing period
- One logical change per commit
- Body paragraph whenever the *why* is not obvious from the subject
- `.env`, `credentials.json`, `token.json`, and service-account JSON verified absent from the diff

REJECT if:
- Vague subjects: `cambios`, `update stuff`, `fix`, `WIP`, `tu mensaje`
- Unrelated concerns bundled in one commit
- Generated artifacts committed: `__pycache__/`, `.venv/`, `node_modules/`, `dist/`,
  `.embeddings_cache.json`, `*.db`
- An agent's contract changed without its consumer changed in the same commit

## Commit language

Subject and body in **English**, even though domain identifiers in the code are Spanish. This is the
one place the repo is inconsistent today; English is the target so `git log` stays greppable
alongside type/scope tokens.

## Before opening a PR

1. Targeted tests for the touched agent pass (see the `testing` skill's coverage map — if the agent
   has no tests, add one).
2. `git --no-pager diff main...HEAD --stat` reviewed for accidental files.
3. `CLAUDE.md` env table and the agent's `.env.example` updated if settings changed.
4. If an A2A contract changed: `registry.json` **and** the matching fallback card updated.
5. A memory note exists in `.harness/memory/` for the change.
