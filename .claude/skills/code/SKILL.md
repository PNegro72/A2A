---
name: code
description: "Universal cross-language coding standards (naming, structure, error handling, secrets, comments). Use when writing or reviewing source files in any language in this repo."
when_to_use: "Any source file, any language."
user-invocable: false
model: sonnet
---

# Skill: Universal Coding Standards

## Rules — enforced now

REJECT if:
- Hardcoded secrets, API keys, tokens, or credentials in source (`CLAUDE_API_KEY`,
  `GOOGLE_API_KEY`, `OPENAI_API_KEY`, `GITHUB_TOKEN`, `TAVILY_API_KEY`, OAuth client secrets)
- Committing `.env`, `credentials.json`, `token.json`, or any service-account JSON
- Silent error handling (`except: pass`, empty `catch {}`)
- `TODO` / `FIXME` without a linked issue number
- Error responses that echo raw upstream bodies or raw exception text to the caller
- Suppressed diagnostics without an inline justification comment
- Hardcoded `localhost:PORT` or model ids in agent code — read from env with the value documented
  in that agent's `.env.example`

REQUIRE:
- Descriptive names; no `data`, `tmp`, `res`, `x` for non-trivial values
- Error messages that identify *what* failed and *with which input*
- Safe client-facing errors; full detail logged server-side
- Every new env var added to the owning agent's `.env.example` **and** the table in `CLAUDE.md`

PREFER:
- Early returns over nested conditionals
- Deleting dead code over commenting it out
- Comments that explain *why*, not *what*

## Language convention — as practised

This is a Spanish-language product with a Spanish-speaking team, and the code reflects that:
domain identifiers are Spanish (`rankear_candidatos`, `generar_preguntas`, `crear_borrador_email`,
`candidatos_rankeados`, `habilidades_faltantes`) and many comments are Spanish.

RULE: **match the file you are editing.** Domain concepts stay in Spanish — renaming them to English
is churn and breaks the mental link to the prompts, which are Spanish. Technical/infrastructure
identifiers (`server`, `timeout`, `payload`, `loader`) stay English. All user-facing output is
Spanish.

REJECT if a change introduces an English alias for an existing Spanish domain concept, or vice
versa, creating two names for one thing.

## Repo layout contract

| Path | Owns |
|---|---|
| `agente_orchestrator/` | Routing, registry, SSE chat API (`:8000`) |
| `agente_job_description/` | JD parsing + drafting (`:8001`) |
| `agente_busquedas_internas/` | Internal candidate ranking, RAGaaS/Qdrant (`:8002`) |
| `agente_entrevistas/` | Interview kits (`:8003`, Flask) |
| `agente_scheduling/` | Google Calendar OAuth2 (`:8004`, Flask) |
| `agente_busquedas_externas/` | External sourcing pipeline (`:8080`) |
| `frontend/` | Angular 18 PWA (`:4200`) |
| `MCP/`, `Qdrant/` | External data-source integrations |
| `.harness/memory/` | Persistent cross-session notes |

Agents talk over **HTTP** only — never a direct cross-agent Python import.

## Shell scripts

`start_all.sh` / `stop_all.sh` are POSIX scripts run under Git Bash on Windows. They assume
`/tmp/sape_logs` and `lsof`. Keep new additions to them Git-Bash-compatible, and add both the start
entry and the port in `stop_all.sh` — the two are currently out of sync (`stop_all.sh` lists port
8006 in one place and omits it in the fallback loop).
