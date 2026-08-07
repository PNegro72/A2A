---
name: testing
description: "pytest and Angular testing standards for this repo: real coverage map, which command to run per agent, and rules for mocking LLM and agent calls. Use when writing or running tests."
when_to_use: "Any file under tests/, *test*.py, or *.spec.ts."
user-invocable: false
model: sonnet
---

# Skill: Testing

## Real coverage map (verified 2026-08-04)

| Agent | Tests | Config |
|---|---|---|
| `agente_orchestrator` | `tests/` | `pytest.ini` |
| `agente_job_description` | `tests/` | `[tool.pytest]` in `pyproject.toml` |
| `agente_busquedas_internas` | `tests/` | `[tool.pytest]` in `pyproject.toml` |
| `agente_busquedas_externas` | `tests/unit/` | `[tool.pytest]` in `pyproject.toml` |
| `agente_entrevistas` | `tests/` | `pytest.ini` |
| `agente_scheduling` | **none** | — |
| `frontend` | `*.spec.ts` | `ng test` (Karma) |

`agente_scheduling` still has no tests. When you change it, add the first one.

## Testing code that imports ADK

`agente_orchestrator/server.py` imports Google ADK, observability instrumentation, and the root
agent at module load. `tests/conftest.py` installs minimal stubs in `sys.modules` **before**
importing it, so the HTTP layer is testable without ADK, credentials, or network. Reuse that
fixture (`server_module`) rather than inventing a second stubbing scheme, and swap `server.runner`
for a fake that yields a fixed event sequence.

Better still: keep new logic out of the ADK-importing module. `request_state.py` has zero ADK and
FastAPI imports, so its 17 tests run anywhere — prefer that shape for new state or policy code.

## Which command to run

```bash
# from the agent directory, in that agent's venv
pytest tests/ -v
pytest tests/test_agente_busquedas_internas.py -v   # single file
cd frontend && npm test
```

Run the **narrowest** command covering the change; escalate only when core behavior changed.

## Rules

REJECT if:
- A test makes a real network call to Claude, Gemini, OpenAI, GitHub, Tavily, Himalayas, or Qdrant
- A test requires a real API key to pass
- A test depends on another agent's server being up — mock `call_external_agent`
- Tests share mutable state or depend on execution order
- A test writes into the repo working tree instead of `tmp_path`
- `.embeddings_cache.json` or the dev SQLite DB is mutated by a test run
- A behavioral change is covered only by "does not raise"

REQUIRE:
- Behavior-describing names: `test_rankea_candidatos_ordena_por_score_descendente`
- One logical assertion target per test
- Fixtures for setup; `tmp_path` for filesystem work
- Contract changes covered by a test asserting the new shape — especially
  `JobDescriptionEstructurada`, which is **duplicated** in `agente_job_description/schemas/` and
  `agente_busquedas_internas/schemas/`: a test should fail if the two copies diverge
- Deterministic scoring tests with fixed inputs asserting exact ordering, not just presence

PREFER:
- `pytest.mark.parametrize` over near-duplicate tests
- Fakes built from the real Pydantic models, so schema drift breaks the test
- Small unit tests; at most a thin smoke test for a full pipeline

```python
# REQUIRE
import pytest


@pytest.fixture
def resultado() -> ResultadoRanking:
    return ResultadoRanking(candidatos_rankeados=[...])


def test_rankea_candidatos_ordena_por_score_descendente(resultado):
    scores = [c.score for c in resultado.candidatos_rankeados]
    assert scores == sorted(scores, reverse=True)
```
