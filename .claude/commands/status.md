Provide a project status overview for the A2A multi-agent recruiting system.

Gather and report, concisely:

1. **Git** — current branch, `git --no-pager log --oneline -10`, uncommitted/untracked files
2. **Stack health** — which agent ports are listening: orchestrator `:8000`, job_description
   `:8001`, busquedas_internas `:8002`, entrevistas `:8003`, scheduling `:8004`,
   busquedas_externas `:8080`, frontend `:4200`
3. **Recent memory** — the last 5 entries in `.harness/memory/index.md`
4. **Open work** — unfinished items from the latest handoff note, plus `TODO`/`FIXME` in tracked
   source
5. **Next priorities** — 3 concrete next actions, ordered

Keep it under 30 lines. No speculation: report only what you verified.
