---
name: code-python
description: "Python standards for this repo, split into enforced rules and target conventions with measured current prevalence. Use when writing or reviewing *.py files."
when_to_use: "Any *.py file in agente_*/, MCP/, or Qdrant/."
user-invocable: false
model: sonnet
---

# Skill: Python

## Declared Python versions (verified)

| Agent | `requires-python` |
|---|---|
| `agente_job_description`, `agente_busquedas_internas` | `>=3.11` |
| `agente_busquedas_externas` | `>=3.12` |
| `agente_orchestrator`, `agente_entrevistas`, `agente_scheduling` | **none declared** (`requirements.txt` only) |

Do not use 3.12-only syntax outside `agente_busquedas_externas`.

## Enforced now — REJECT on sight

- Bare `except:` (or `except Exception:` that swallows without re-raise or a handled outcome)
- Mutable default arguments (`def f(x=[])`)
- Logging secret **values** (log the variable name or source, never the value)
- `assert` used for runtime validation
- An outbound HTTP call without an explicit `timeout`
- Blocking I/O (`requests`, `time.sleep`) inside an `async def`
- A required setting read with a silent `None` fallback that explodes downstream — either give a
  documented default or fail loudly at startup, as `AGENT_HTTP_TIMEOUT` does
- Pydantic v1 style (`class Config:`) — the repo is **Pydantic v2** (`pydantic>=2.0.0`); use
  `model_config` and `model_validator`

```python
# REJECT
def rank(candidates=[]):
    try:
        return score(candidates)
    except:
        print("failed")
```

## Target convention — apply to code you touch

These are **not** yet the norm. Measured prevalence across 110 `.py` files (2026-08-04):

| Convention | Current | Rule |
|---|---|---|
| `from __future__ import annotations` | 3.6% (4/110) | Add to new modules; do not bulk-retrofit |
| `pathlib` over `os.path` | 10% vs 8.2% | New filesystem code uses `pathlib` |
| `logging` over `print()` | 17.3% vs 8.2% | New code uses `logging`; convert `print()` in any function you modify |
| Type hints on public functions | partial | Full hints on anything you add or change |

Do not open a refactor PR to make the whole repo comply. Converge file by file, as part of changes
that were happening anyway.

## HTTP clients — both are in use, deliberately

| Client | Where | Rule |
|---|---|---|
| `requests` (sync) | `agente_orchestrator/tools/call_external_agent.py`, `registry/loader.py`, `agente_entrevistas/tools/web_search.py` | The orchestrator delegation path is synchronous. **Do not convert it to async as a side effect** of another change — it is load-bearing and untested |
| `httpx` | `agente_busquedas_externas/src/agents/sourcing/github.py`, `agente_entrevistas/tools/crear_borrador_email.py` | Preferred for new async code |

Either way: explicit `timeout`, and exceptions mapped to a structured result rather than propagated
raw to the caller.

```python
# REQUIRE — new async code
from __future__ import annotations

import logging

import httpx
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


class CandidatoRankeado(BaseModel):
    candidato: str
    score: float = Field(ge=0.0, le=1.0)
    justificacion: str


async def fetch_card(url: str, *, timeout: float = 10.0) -> dict:
    async with httpx.AsyncClient(timeout=timeout) as client:
        try:
            response = await client.get(url)
            response.raise_for_status()
        except httpx.HTTPError as exc:
            logger.error("agent card fetch failed url=%s: %s", url, exc)
            raise
    return response.json()
```

PREFER:
- `list[str]` / `dict[str, int]` over `typing.List` / `Dict`
- Lazy `%s` log formatting, not f-strings inside log calls
- Pydantic models over raw `dict` for anything crossing an agent boundary

## Environment & dependencies

- Each agent owns its venv. Never install into another agent's environment.
- `pyproject.toml` agents (`job_description`, `busquedas_internas`, `busquedas_externas`):
  `pip install -e ".[dev]"`.
- `requirements.txt` agents (`orchestrator`, `entrevistas`, `scheduling`):
  `pip install -r requirements.txt`.
- A new dependency lands in the owning agent's manifest in the same change.
