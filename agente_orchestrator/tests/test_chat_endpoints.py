"""Tests del transporte HTTP del orchestrator, con foco en `GET /chat/status/{id}`.

El agente está reemplazado por un doble: estos tests verifican el cableado de los
endpoints, no la calidad de las respuestas del LLM.
"""

from __future__ import annotations

import asyncio
from typing import Any

import pytest
from fastapi.testclient import TestClient

from conftest import FakeContent, FakePart


class FakeEvent:
    def __init__(self, parts: list[Any], final: bool = False) -> None:
        self.content = FakeContent(role="model", parts=parts)
        self._final = final

    def is_final_response(self) -> bool:
        return self._final


class FakeRunner:
    """Emite una secuencia fija de eventos ADK."""

    def __init__(self, events: list[FakeEvent], fail_with: Exception | None = None) -> None:
        self._events = events
        self._fail_with = fail_with

    async def run_async(self, **kwargs: Any):
        for event in self._events:
            await asyncio.sleep(0)
            yield event
        if self._fail_with:
            raise self._fail_with


def _final_event(text: str) -> FakeEvent:
    return FakeEvent([FakePart(text=text)], final=True)


@pytest.fixture
def client(server_module):
    with TestClient(server_module.app) as test_client:
        yield test_client


@pytest.fixture(autouse=True)
def reset_state(server_module):
    yield
    server_module.pending_requests.clear()
    server_module.request_states = type(server_module.request_states)()


def _start_chat(client: TestClient, message: str = "hola") -> str:
    response = client.post("/chat", json={"message": message})
    assert response.status_code == 200
    return response.json()["request_id"]


def _poll_until_settled(client: TestClient, request_id: str, intentos: int = 50) -> dict:
    for _ in range(intentos):
        payload = client.get(f"/chat/status/{request_id}").json()
        if payload["status"] in ("done", "error"):
            return payload
    raise AssertionError(f"el request nunca terminó: {payload}")


def test_post_chat_devuelve_ids_y_stream_url(client: TestClient):
    body = client.post("/chat", json={"message": "hola"}).json()

    assert body["request_id"]
    assert body["conversation_id"]
    assert body["stream_url"] == f"/chat/stream/{body['request_id']}"


def test_status_de_request_inexistente_devuelve_404(client: TestClient):
    assert client.get("/chat/status/no-existe").status_code == 404


def test_status_devuelve_la_respuesta_final(client: TestClient, server_module):
    server_module.runner = FakeRunner([_final_event("listo")])
    request_id = _start_chat(client)

    payload = _poll_until_settled(client, request_id)

    assert payload["status"] == "done"
    assert payload["final"] == {"role": "assistant", "content": "listo"}
    assert payload["error"] is None


def test_status_cierra_con_error_si_no_hay_respuesta_final(client: TestClient, server_module):
    """Sin esto el cliente quedaría polleando para siempre."""
    server_module.runner = FakeRunner([])
    request_id = _start_chat(client)

    payload = _poll_until_settled(client, request_id)

    assert payload["status"] == "error"
    assert payload["error"]["code"] == "NO_FINAL_RESPONSE"


def test_status_no_filtra_el_detalle_de_la_excepcion(client: TestClient, server_module):
    server_module.runner = FakeRunner([], fail_with=RuntimeError("connection string secreta"))
    request_id = _start_chat(client)

    payload = _poll_until_settled(client, request_id)

    assert payload["status"] == "error"
    assert payload["error"]["code"] == "ORCHESTRATOR_ERROR"
    assert "secreta" not in payload["error"]["message"]


def test_un_request_id_se_consume_una_sola_vez(client: TestClient, server_module):
    server_module.runner = FakeRunner([_final_event("listo")])
    request_id = _start_chat(client)

    _poll_until_settled(client, request_id)

    assert client.get(f"/chat/stream/{request_id}").status_code == 404


def test_el_stream_sse_sigue_funcionando(client: TestClient, server_module):
    server_module.runner = FakeRunner([_final_event("listo")])
    request_id = _start_chat(client)

    response = client.get(f"/chat/stream/{request_id}")

    assert response.status_code == 200
    assert "event: final" in response.text
    assert "listo" in response.text


def test_el_stream_sse_cierra_con_error_si_no_hay_respuesta_final(
    client: TestClient, server_module
):
    """Gemelo SSE de `test_status_cierra_con_error_si_no_hay_respuesta_final`.

    Sin un evento terminal el StreamingResponse cierra limpio, el browser
    reconecta por spec de EventSource y se come un 404 (el request_id ya fue
    consumido), así que el usuario ve un "conexión cerrada" espurio en lugar
    del motivo real.
    """
    server_module.runner = FakeRunner([])
    request_id = _start_chat(client)

    response = client.get(f"/chat/stream/{request_id}")

    assert response.status_code == 200
    assert "event: error" in response.text
    assert "NO_FINAL_RESPONSE" in response.text


def test_health_reporta_los_requests_en_seguimiento(client: TestClient):
    body = client.get("/health").json()

    assert body["status"] == "ok"
    assert "pending_requests" in body
    assert "tracked_requests" in body


class SlowRunner:
    """Nunca emite un evento: simula una corrida colgada."""

    async def run_async(self, **kwargs: Any):
        await asyncio.sleep(30)
        yield _final_event("tarde")


def test_una_corrida_colgada_termina_el_polling_con_timeout(
    client: TestClient, server_module, monkeypatch
):
    monkeypatch.setattr(server_module, "RUN_TIMEOUT_SECONDS", 0.05)
    server_module.runner = SlowRunner()
    request_id = _start_chat(client)

    payload = _poll_until_settled(client, request_id, intentos=200)

    assert payload["status"] == "error"
    assert payload["error"]["code"] == "RUN_TIMEOUT"


def test_los_requests_pendientes_nunca_reclamados_se_purgan(
    client: TestClient, server_module, monkeypatch
):
    abandonado = _start_chat(client)
    assert abandonado in server_module.pending_requests

    monkeypatch.setattr(server_module, "PENDING_TTL_SECONDS", -1)
    _start_chat(client)

    assert abandonado not in server_module.pending_requests


def test_purgar_pendientes_no_toca_los_recien_creados(client: TestClient, server_module):
    primero = _start_chat(client)
    segundo = _start_chat(client)

    assert primero in server_module.pending_requests
    assert segundo in server_module.pending_requests
