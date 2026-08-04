---
date: 2026-08-04
type: convention
topic: harness
---

# Agent Harness — Structure and Rationale

## Context

The project needed the ergonomics of the `Invincible` harness (skill-driven standards, session
memory, slash commands) without becoming an Invincible-managed repository. No `invincible` CLI
dependency, no `invincible update` propagation, no hub state.

## What was decided

Three layers, all plain markdown:

1. `AGENTS.md` — single entry point. Skill index (trigger → skill path), mandatory session
   protocol, universal rules, cross-agent change checklist, engineering persona.
2. `.claude/skills/<name>/SKILL.md` — enforceable REJECT / REQUIRE / PREFER rules with short code
   examples. Two tiers: language skills (`code`, `code-python`, `typescript-angular`) and
   project-extension skills (`python-adk-agents`, `agent-registry`). Both load when both triggers
   match; the more specific one wins.
3. `.claude/commands/*.md` — `/review`, `/status`, `/sync-memory`, `/handoff`, `/new-agent`.

Memory replaces Invincible's `invincible memory save` CLI with committed markdown under
`.harness/memory/` (`index.md` + `notes/` + `sessions/`). Committed on purpose: the point is shared
team context, not per-developer scratch.

## Why

The value in Invincible is the *convention*, not the tooling. Markdown files that every agent reads
natively give ~90% of the benefit at ~0 maintenance cost, and the harness cannot break the build.

## Impact on future work

- Adding a skill = new `SKILL.md` + a row in `AGENTS.md` Skill Index + a row in
  `.harness/skill-registry.md`. Three edits, no code.
- `.gitignore` previously ignored `AGENTS.md` (leftover from NERV scaffolding); that line was
  removed so the harness entry point is tracked.
- Deliberately omitted: hooks, SDD workflow, wiki sync, adversarial dual-model review. Add only if
  the pain becomes real.
