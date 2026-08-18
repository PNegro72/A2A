Scaffold and register a new agent: $ARGUMENTS

`$ARGUMENTS` is the agent name in snake_case (e.g. `referencias_laborales`) plus, optionally, a
one-line purpose and a preferred port.

## Procedure

1. Load `.claude/skills/python-adk-agents/SKILL.md` and `.claude/skills/agent-registry/SKILL.md`.
2. Ask the user for anything missing: purpose, model (Claude vs Gemini), port, external data
   sources. Do not guess the purpose.
3. Pick a free port — the assigned map is orchestrator `:8000`, job_description `:8001`,
   busquedas_internas `:8002`, entrevistas `:8003`, scheduling `:8004`, busquedas_externas `:8080`,
   frontend `:4200`. `stop_all.sh` also references `:8006`; treat it as taken.
4. Create `agente_<name>/` using the `agentes/<name>/` + `schemas/` + `tests/` shape (the closest
   thing to a house style — see the layout table in the ADK skill; do not assume every agent
   matches it). FastAPI for new agents.
5. Define the agent's Pydantic v2 input/output contract before writing any logic.
6. Expose `POST /a2a/<name>` and `GET /health`.
7. Register it: `registry/registry.json` entry, `<NAME>_AGENT_CARD_URL` in the orchestrator's
   `.env.example`, and `registry/fallback_cards/<name>_agent.json` — full schema, prose in English.
8. Add it to `start_all.sh` and to **both** the port list and the fallback loop in `stop_all.sh`.
9. Document it in root `CLAUDE.md`: architecture diagram, run command, env var table.
10. Add at least one test validating the output contract with mocked LLM/HTTP calls.
11. Verify: start the agent, `curl` its `/health`, then send a `POST /chat` prompt through the
    orchestrator that should route to it and confirm the delegation in the logs.
12. Write a memory note via `/sync-memory`.

Do not mark this done until step 11 passes.
