# A2A Agent Harness

Invincible-inspired, **standalone** — no external CLI, no managed-repo tooling. Everything here is
plain markdown that any coding agent (Claude Code, Copilot CLI, Cursor) reads directly.

## Layout

| Path | Purpose |
|---|---|
| `../AGENTS.md` | Entry point: skill index, session protocol, universal rules, persona |
| `../CLAUDE.md` | Architecture reference (what the system *is*) |
| `../.claude/skills/*/SKILL.md` | Enforceable rules, loaded by file-type trigger |
| `../.claude/commands/*.md` | Slash commands (`/review`, `/status`, `/sync-memory`, `/handoff`, `/new-agent`) |
| `memory/index.md` | Chronological index of everything learned |
| `memory/notes/` | Durable topic-scoped knowledge (incl. `known-drift.md`) |
| `memory/sessions/` | Per-session summaries and handoffs |
| `memory/sdd/` | Spec + verification artifacts for larger changes |
| `skill-registry.md` | Human-readable table of installed skills |
| `verify.py` | Self-check: runs the harness acceptance criteria (stdlib only) |

## Contract

1. **Session start** → read `memory/index.md`, grep `memory/` for the topic.
2. **During work** → load the skills whose triggers match the files you touch.
3. **Session end** → `/sync-memory` (or `/handoff` if unfinished).

## Keeping it honest

The skills quote real routes, ports, model fields, and function signatures. That is why they are
useful — and why they rot. After changing the harness, or after changing an orchestrator route, an
agent port, or a shared schema:

```bash
python .harness/verify.py     # 20 acceptance criteria, exit 0 = green
```

It has no dependencies and is not wired into CI or any build. A claim the harness cannot verify is
a claim it should not make.

## Adding a skill

1. Create `.claude/skills/<name>/SKILL.md` with YAML frontmatter
   (`name`, `description`, `when_to_use`, `user-invocable`, `model`).
2. Add a trigger row to the Skill Index in `AGENTS.md`.
3. Add a row to `skill-registry.md`.
4. Run `python .harness/verify.py`.

Rules are written as **REJECT / REQUIRE / PREFER** blocks with short code examples. Keep each skill
under ~150 lines — long skills get skimmed, short ones get followed.

## Not included on purpose

No hooks, no state machine, no SDD workflow, no wiki sync, no memory daemon. Add them only when the
pain is real.
