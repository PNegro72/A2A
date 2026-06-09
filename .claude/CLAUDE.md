<!-- INVINCIBLE:START -->
## Agent Infrastructure

This project uses **invincible** for agent-native engineering.

- **Stack**: generic
- **Shared Task Hub**: use `invincible hub ...` directly; no background server is required
- **Memory & Hub**: CLI only — `invincible memory …` / `invincible hub …`

### Coding Standards

See [`AGENTS.md`](AGENTS.md) for project coding standards and the [`skills/`](skills/) directory for modular rules. Load relevant skills based on the files you are working on.

### Quick Commands
- `/architect` — Design architecture with structured output
- `/review` — Code review with findings report
- `/handoff` — Create agent handoff document
- `/sync-memory` — Sync session to persistent memory
- `/status` — Project status overview
- `/sdd-new <change>` — Start an SDD workflow (explore → propose → spec → design → tasks → apply → verify → archive)
- `/judgment-day` — Dual-model adversarial review (Claude + Copilot via hub)
- `/docs [scope]` — Generate or refresh the `docs/` set with Mermaid diagrams (architecture, surface, data flow, models, onboarding, …)

### SDD Workflow

`.claude/skills/` contains SDD phase skills (agentskills.io format — loaded by both Claude Code and VS Code Copilot).
The orchestrator at `.claude/commands/sdd-new.md` invokes each phase skill inline via the `Skill` tool — no sub-agent spawning.
Use `/sdd-new` to run the full workflow. Each phase saves artifacts to memory with `topic_key: sdd-<change_id>-<phase>`.
<!-- INVINCIBLE:END -->
