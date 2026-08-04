---
name: agent-registry
description: "How to register, modify, or remove an agent in agente_orchestrator/registry — registry.json entries, card env vars, and the real fallback-card schema. Use when adding or changing an agent's A2A surface."
when_to_use: "Adding a new agent, renaming one, changing its URL/port, or changing its advertised actions."
user-invocable: false
model: sonnet
---

# Skill: Agent Registry

The orchestrator discovers agents from `agente_orchestrator/registry/registry.json`, loaded by
`registry/loader.py`. **Adding an agent needs no orchestrator code change** — only registry data, an
env var, and a fallback card.

## registry.json entry

```json
{
  "name": "<snake_case>_agent",
  "card_url_env": "<UPPER_SNAKE>_AGENT_CARD_URL",
  "fallback_path": "fallback_cards/<snake_case>_agent.json"
}
```

Currently registered (5): `scheduling_agent`, `busquedas_internas_agent`, `job_description_agent`,
`entrevistas_agent`, `busquedas_externas_agent` — each with a matching file in `fallback_cards/`.

## Fallback card schema — real keys

```jsonc
{
  "name": "job_description_agent",
  "version": "1.0.0",
  "description": "...",          // what the agent does — the orchestrator routes on this
  "when_to_use": "...",          // explicit trigger conditions, incl. ordering vs other agents
  "webhook_url": "http://localhost:8001/a2a/job_description",
  "http_method": "POST",
  "actions": [
    {
      "name": "parsear_jd",
      "description": "...",
      "request_schema": { "action": "parsear_jd", "jd_texto": "string — ..." },
      "possible_responses": [
        { "status": "ok",    "fields": ["role_title", "..."] },
        { "status": "error", "fields": ["message"] }
      ]
    }
  ],
  "conventions": { "<key>": "prose describing an output guarantee" }
}
```

Card prose (`description`, `when_to_use`, `actions[].description`, `conventions`) is written in
**English**, even though the product UX is Spanish. Match the existing cards.

`conventions` is not decoration — it encodes output guarantees the orchestrator relies on (enum
values, formatting, statelessness). If behavior changes, the convention text changes with it.

## Port map (verified)

| Port | Agent |
|---|---|
| 8000 | orchestrator |
| 8001 | job_description (`/a2a/job_description`, `/a2a/redactar_jd`) |
| 8002 | busquedas_internas |
| 8003 | entrevistas |
| 8004 | scheduling (`/scheduling-agent`) |
| 8080 | busquedas_externas |
| 4200 | frontend |

`stop_all.sh` also references 8006 — unassigned; do not reuse it without checking.

## Checklist — adding an agent

1. Append the entry to `registry/registry.json`.
2. Add `<UPPER_SNAKE>_AGENT_CARD_URL` to `agente_orchestrator/.env.example`.
3. Create `registry/fallback_cards/<name>_agent.json` using the schema above, with every action's
   `request_schema` and `possible_responses` filled in.
4. Document the agent, port, and env vars in root `CLAUDE.md`.
5. Add it to `start_all.sh` and to **both** the port list and the fallback loop in `stop_all.sh`.
6. Verify end-to-end: start the stack, `POST /chat` with a prompt that should route to it, confirm
   delegation in the orchestrator logs.

REJECT if:
- A `registry.json` entry has no matching fallback card, or vice versa
- A card advertises an action the agent does not implement — the orchestrator will route to a
  capability that does not exist and the recruiter gets a dead end
- A card URL is hardcoded in `registry.json` instead of referenced via `card_url_env`
- An agent is removed from `registry.json` but its env var and fallback card are left behind
- The `webhook_url` in the card disagrees with the agent's actual route or port
- A new port collides with the table above
