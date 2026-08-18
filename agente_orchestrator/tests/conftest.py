"""Stubs para poder importar `server.py` sin ADK, sin credenciales y sin red.

`server.py` importa Google ADK, la instrumentación de observabilidad y el agente
raíz en tiempo de import. Nada de eso hace falta para testear el transporte HTTP,
así que se reemplaza por dobles mínimos antes de importarlo.
"""

from __future__ import annotations

import sys
import types as pytypes
from typing import Any

import pytest

REQUIRED_ENV = {
    "HOST": "localhost",
    "PORT": "8000",
    "LOG_LEVEL": "info",
    "CORS_ALLOWED_ORIGINS": "http://localhost:4200",
    "AGENT_HTTP_TIMEOUT": "120",
}


class FakePart:
    def __init__(self, text: str | None = None) -> None:
        self.text = text
        self.function_call = None
        self.function_response = None


class FakeContent:
    def __init__(self, role: str = "user", parts: list[Any] | None = None) -> None:
        self.role = role
        self.parts = parts or []


class FakeSessionService:
    async def create_session(self, **kwargs: Any) -> None:
        return None


def _install_stub_modules() -> None:
    adk = pytypes.ModuleType("google.adk")
    runners = pytypes.ModuleType("google.adk.runners")
    sessions = pytypes.ModuleType("google.adk.sessions")
    genai = pytypes.ModuleType("google.genai")
    google = sys.modules.get("google") or pytypes.ModuleType("google")

    class Runner:
        def __init__(self, **kwargs: Any) -> None:
            self.kwargs = kwargs

    runners.Runner = Runner
    sessions.InMemorySessionService = FakeSessionService
    genai.types = pytypes.SimpleNamespace(Content=FakeContent, Part=FakePart)

    observability = pytypes.ModuleType("observability")
    observability.init_observability = lambda *args, **kwargs: None

    agent = pytypes.ModuleType("agent")
    agent.root_agent = object()

    sys.modules.update({
        "google": google,
        "google.adk": adk,
        "google.adk.runners": runners,
        "google.adk.sessions": sessions,
        "google.genai": genai,
        "observability": observability,
        "agent": agent,
    })


@pytest.fixture(scope="session")
def server_module(tmp_path_factory: pytest.TempPathFactory):
    """Importa `server.py` una sola vez, con las dependencias pesadas stubbeadas."""
    import os

    for key, value in REQUIRED_ENV.items():
        os.environ.setdefault(key, value)

    _install_stub_modules()

    import server  # noqa: PLC0415 — el import tiene que ocurrir después de los stubs

    return server
