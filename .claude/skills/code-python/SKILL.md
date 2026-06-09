---
name: code-python
description: "Python language standards for invincible-based projects: type hints, error handling, logging, and style conventions."
when_to_use: "When writing or reviewing *.py source files in any project."
user-invocable: false
model: sonnet
effort: medium
hub-skill-ids: [implementation, review, refactoring]
---

# Skill: Python

## Rules

REJECT if:
- Missing type hints on public functions or methods
- Bare `except:` without a specific exception type
- `print()` used in production code (use `logging` instead)
- Mutable default arguments (e.g., `def f(x=[]):`)
- `os.path` used for filesystem operations

```python
# REJECT
def process(items=[]):
    try:
        result = fetch(items)
    except:
        print("failed")
    return os.path.join(base, "out")
```

REQUIRE:
- `from __future__ import annotations` at the top of every module
- Type hints on all public functions and class attributes
- Pydantic v2 for data validation models
- `pathlib.Path` over `os.path` for all filesystem operations

```python
# REQUIRE
from __future__ import annotations
from pathlib import Path
import logging

logger = logging.getLogger(__name__)

def process(items: list[str]) -> list[str]:
    try:
        return fetch(items)
    except ValueError as exc:
        logger.error("fetch failed: %s", exc)
        raise
```

PREFER:
- Early returns over deeply nested conditionals
- `dataclasses` or Pydantic models over raw `dict` for structured data
- `logging` module over `print()` everywhere

```python
# PREFER
from dataclasses import dataclass

@dataclass
class Config:
    host: str
    port: int = 8080

def validate(cfg: Config) -> bool:
    if not cfg.host:
        return False
    return cfg.port > 0
```
