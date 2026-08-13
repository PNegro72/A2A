"""Tests de `tools/call_external_agent.py`, con foco en el presupuesto de tiempo por agente.

La tool nunca levanta excepciones: siempre devuelve un dict. Estos tests verifican
el contrato de ese dict y que el timeout correcto llegue a `requests.post`, sin
tocar la red.
"""

from __future__ import annotations

import os

import pytest

# La tool lee el timeout global en tiempo de import y falla fuerte si falta.
os.environ.setdefault("AGENT_HTTP_TIMEOUT", "120")

from requests.exceptions import Timeout  # noqa: E402

from tools import call_external_agent as cea  # noqa: E402

EXTERNAS = "busquedas_externas_agent"
INTERNAS = "busquedas_internas_agent"


@pytest.fixture(autouse=True)
def registry_falso(monkeypatch: pytest.MonkeyPatch):
    """Dos agentes registrados, ambos con webhook."""
    monkeypatch.setattr(
        cea,
        "get_registry",
        lambda: {
            EXTERNAS: {"webhook_url": "http://127.0.0.1:8080/a2a/busquedas_externas"},
            INTERNAS: {"webhook_url": "http://127.0.0.1:8002/a2a/busquedas_internas"},
        },
    )


class TestParseTimeoutOverrides:
    def test_parsea_varias_entradas(self):
        assert cea._parse_timeout_overrides("a:30,b:45") == {"a": 30, "b": 45}

    def test_tolera_espacios_y_entradas_vacias(self):
        assert cea._parse_timeout_overrides(" a : 30 , , b:45 ") == {"a": 30, "b": 45}

    def test_string_vacio_no_da_overrides(self):
        assert cea._parse_timeout_overrides("") == {}

    @pytest.mark.parametrize("crudo", ["a:abc", "a:0", "a:-5", ":30", "a:", "sin-dos-puntos"])
    def test_una_entrada_invalida_se_descarta_en_vez_de_romper(self, crudo: str):
        """Un override mal escrito tiene que degradar al timeout global, no tumbar el arranque."""
        assert cea._parse_timeout_overrides(crudo) == {}

    def test_una_entrada_invalida_no_se_lleva_a_las_validas(self):
        assert cea._parse_timeout_overrides("a:abc,b:45") == {"b": 45}


class TestPresupuestoPorAgente:
    def test_el_agente_con_override_usa_su_presupuesto(self, monkeypatch: pytest.MonkeyPatch):
        capturado: dict = {}

        def fake_post(url, **kwargs):
            capturado.update(kwargs)
            raise Timeout()

        monkeypatch.setattr(cea, "AGENT_HTTP_TIMEOUT_OVERRIDES", {EXTERNAS: 30})
        monkeypatch.setattr(cea.requests, "post", fake_post)

        cea.call_external_agent(EXTERNAS, {"action": "buscar_candidatos_externos"})

        assert capturado["timeout"] == 30

    def test_un_agente_sin_override_usa_el_timeout_global(self, monkeypatch: pytest.MonkeyPatch):
        capturado: dict = {}

        def fake_post(url, **kwargs):
            capturado.update(kwargs)
            raise Timeout()

        monkeypatch.setattr(cea, "AGENT_HTTP_TIMEOUT_OVERRIDES", {EXTERNAS: 30})
        monkeypatch.setattr(cea, "AGENT_HTTP_TIMEOUT", 120)
        monkeypatch.setattr(cea.requests, "post", fake_post)

        cea.call_external_agent(INTERNAS, {"action": "buscar_candidatos"})

        assert capturado["timeout"] == 120


class TestFallbackPorTimeout:
    def test_el_timeout_se_marca_degradado_para_que_el_orchestrator_siga(
        self, monkeypatch: pytest.MonkeyPatch
    ):
        """Sin `degraded` el LLM no sabe distinguir "seguí sin esto" de un error real."""
        monkeypatch.setattr(cea, "AGENT_HTTP_TIMEOUT_OVERRIDES", {EXTERNAS: 30})
        monkeypatch.setattr(cea.requests, "post", lambda url, **kw: (_ for _ in ()).throw(Timeout()))

        result = cea.call_external_agent(EXTERNAS, {"action": "buscar_candidatos_externos"})

        assert result["status"] == "error"
        assert result["code"] == "AGENT_TIMEOUT"
        assert result["degraded"] is True
        assert "30s" in result["message"]

    def test_el_mensaje_le_prohibe_reintentar_e_inventar(self, monkeypatch: pytest.MonkeyPatch):
        monkeypatch.setattr(cea, "AGENT_HTTP_TIMEOUT_OVERRIDES", {EXTERNAS: 30})
        monkeypatch.setattr(cea.requests, "post", lambda url, **kw: (_ for _ in ()).throw(Timeout()))

        message = cea.call_external_agent(EXTERNAS, {"action": "x"})["message"]

        assert "Do NOT retry" in message
        assert "do NOT invent" in message

    def test_una_respuesta_ok_no_queda_marcada_como_degradada(
        self, monkeypatch: pytest.MonkeyPatch
    ):
        class FakeResponse:
            status_code = 200

            @staticmethod
            def json():
                return {"status": "exito", "candidates": [{"name": "Alguien"}]}

        monkeypatch.setattr(cea, "AGENT_HTTP_TIMEOUT_OVERRIDES", {EXTERNAS: 30})
        monkeypatch.setattr(cea.requests, "post", lambda url, **kw: FakeResponse())

        result = cea.call_external_agent(EXTERNAS, {"action": "x"})

        assert result["status"] == "exito"
        assert "degraded" not in result
