"""Tests de la máquina de estados que respalda `GET /chat/status/{request_id}`.

No importan `server.py` a propósito: el objetivo es poder correrlos sin ADK,
sin credenciales y sin red.
"""

from __future__ import annotations

import pytest

from request_state import NO_FINAL_RESPONSE_CODE, RequestStateStore

REQUEST_ID = "req-1"


class FakeClock:
    """Reloj controlable para testear el TTL sin dormir."""

    def __init__(self) -> None:
        self.now = 0.0

    def __call__(self) -> float:
        return self.now

    def advance(self, seconds: float) -> None:
        self.now += seconds


@pytest.fixture
def store() -> RequestStateStore:
    store = RequestStateStore()
    store.start(REQUEST_ID)
    return store


def test_request_desconocido_devuelve_none():
    assert RequestStateStore().snapshot("inexistente") is None


def test_request_recien_iniciado_esta_running(store: RequestStateStore):
    snapshot = store.snapshot(REQUEST_ID)
    assert snapshot == {"status": "running", "steps": [], "final": None, "error": None}


def test_los_pasos_se_acumulan_en_orden(store: RequestStateStore):
    store.add_step(REQUEST_ID, {"agent": "job_description_agent", "status": "running",
                                "message": "primero", "timestamp": "t1"})
    store.add_step(REQUEST_ID, {"agent": "job_description_agent", "status": "done",
                                "message": "segundo", "timestamp": "t2"})

    mensajes = [step["message"] for step in store.snapshot(REQUEST_ID)["steps"]]
    assert mensajes == ["primero", "segundo"]


def test_snapshot_devuelve_una_copia_de_los_pasos(store: RequestStateStore):
    store.add_step(REQUEST_ID, {"agent": "a", "status": "done", "message": "m", "timestamp": "t"})

    store.snapshot(REQUEST_ID)["steps"].clear()

    assert len(store.snapshot(REQUEST_ID)["steps"]) == 1


def test_respuesta_final_marca_el_request_como_done(store: RequestStateStore):
    store.set_final(REQUEST_ID, {"role": "assistant", "content": "listo"})

    snapshot = store.snapshot(REQUEST_ID)
    assert snapshot["status"] == "done"
    assert snapshot["final"]["content"] == "listo"


def test_error_marca_el_request_como_error(store: RequestStateStore):
    store.set_error(REQUEST_ID, "ORCHESTRATOR_ERROR", "falló")

    snapshot = store.snapshot(REQUEST_ID)
    assert snapshot["status"] == "error"
    assert snapshot["error"] == {"code": "ORCHESTRATOR_ERROR", "message": "falló"}


def test_finish_sin_respuesta_final_cierra_con_error(store: RequestStateStore):
    """Si no cerrara, el cliente quedaría polleando para siempre."""
    store.finish(REQUEST_ID)

    snapshot = store.snapshot(REQUEST_ID)
    assert snapshot["status"] == "error"
    assert snapshot["error"]["code"] == NO_FINAL_RESPONSE_CODE


def test_finish_no_pisa_la_respuesta_final(store: RequestStateStore):
    store.set_final(REQUEST_ID, {"role": "assistant", "content": "listo"})

    store.finish(REQUEST_ID)

    snapshot = store.snapshot(REQUEST_ID)
    assert snapshot["status"] == "done"
    assert snapshot["error"] is None


def test_finish_no_pisa_un_error_previo(store: RequestStateStore):
    store.set_error(REQUEST_ID, "ORCHESTRATOR_ERROR", "falló")

    store.finish(REQUEST_ID)

    assert store.snapshot(REQUEST_ID)["error"]["code"] == "ORCHESTRATOR_ERROR"


@pytest.mark.parametrize("operacion", ["add_step", "set_final", "set_error", "finish"])
def test_operar_sobre_un_request_desconocido_no_explota(operacion: str):
    """El acumulador corre en background: no debe romper por un id vencido."""
    store = RequestStateStore()
    argumentos = {
        "add_step": ({"agent": "a", "status": "done", "message": "m", "timestamp": "t"},),
        "set_final": ({"role": "assistant", "content": "c"},),
        "set_error": ("CODE", "mensaje"),
        "finish": (),
    }[operacion]

    getattr(store, operacion)("desconocido", *argumentos)

    assert store.snapshot("desconocido") is None


def test_purge_conserva_los_requests_en_curso():
    clock = FakeClock()
    store = RequestStateStore(ttl_seconds=60, clock=clock)
    store.start(REQUEST_ID)

    clock.advance(600)

    assert store.purge_expired() == 0
    assert store.is_tracked(REQUEST_ID)


def test_purge_conserva_los_terminados_dentro_del_ttl():
    clock = FakeClock()
    store = RequestStateStore(ttl_seconds=60, clock=clock)
    store.start(REQUEST_ID)
    store.set_final(REQUEST_ID, {"role": "assistant", "content": "listo"})

    clock.advance(59)

    assert store.purge_expired() == 0
    assert store.is_tracked(REQUEST_ID)


def test_purge_elimina_los_terminados_vencidos():
    clock = FakeClock()
    store = RequestStateStore(ttl_seconds=60, clock=clock)
    store.start(REQUEST_ID)
    store.set_final(REQUEST_ID, {"role": "assistant", "content": "listo"})

    clock.advance(61)

    assert store.purge_expired() == 1
    assert not store.is_tracked(REQUEST_ID)
    assert store.snapshot(REQUEST_ID) is None


def test_start_reinicia_el_estado_previo(store: RequestStateStore):
    store.set_error(REQUEST_ID, "ORCHESTRATOR_ERROR", "falló")

    store.start(REQUEST_ID)

    assert store.snapshot(REQUEST_ID) == {
        "status": "running", "steps": [], "final": None, "error": None,
    }


def test_purge_elimina_una_corrida_colgada_en_running():
    clock = FakeClock()
    store = RequestStateStore(ttl_seconds=60, clock=clock, max_running_seconds=300)
    store.start(REQUEST_ID)

    clock.advance(301)

    assert store.purge_expired() == 1
    assert not store.is_tracked(REQUEST_ID)


def test_purge_respeta_una_corrida_running_dentro_del_limite():
    clock = FakeClock()
    store = RequestStateStore(ttl_seconds=60, clock=clock, max_running_seconds=300)
    store.start(REQUEST_ID)

    clock.advance(299)

    assert store.purge_expired() == 0
    assert store.is_tracked(REQUEST_ID)
