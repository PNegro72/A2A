import json
import pytest
from unittest.mock import patch, MagicMock
import agente_entrevistas.tools.generar_preguntas as _gp_mod


RESPUESTA_VALIDA = {
    "total": 3,
    "preguntas": [
        {"categoria": "técnica",    "pregunta": "¿Cómo implementaron idempotencia en Mercado Pago?", "objetivo": "Evaluar sistemas distribuidos", "nivel": "senior", "tiempo_estimado_min": 8},
        {"categoria": "conductual", "pregunta": "Contame de una decisión difícil bajo presión.",      "objetivo": "Evaluar ownership",            "nivel": "senior", "tiempo_estimado_min": 6},
        {"categoria": "presión",    "pregunta": "Tenés Kafka. ¿Qué es un consumer group?",            "objetivo": "Detectar conocimiento real",    "nivel": "senior", "tiempo_estimado_min": 5},
    ],
    "duracion_estimada_min": 19,
}


def _mock_client(payload):
    """Mock del cliente Anthropic — simula response.content[0].text"""
    m = MagicMock()
    msg = MagicMock()
    msg.content = [MagicMock(text=json.dumps(payload))]
    m.messages.create.return_value = msg
    return m


class TestGenerarPreguntas:

    def test_retorna_preguntas_validas(self, candidato_data, proceso_data):
        mock_client = _mock_client(RESPUESTA_VALIDA)
        with patch.object(_gp_mod, "_get_client", return_value=mock_client):
            from agente_entrevistas.tools.generar_preguntas import generar_preguntas
            result = generar_preguntas(candidato_nombre=candidato_data["nombre"], skills=candidato_data["skills"], experiencia=candidato_data["experiencia"], cv_texto=candidato_data["cv_texto"], jd_texto=proceso_data["jd_texto"], info_publica=None)

        assert "error" not in result
        assert result["total"] == 3
        assert result["duracion_estimada_min"] == 19

    def test_preguntas_tienen_categorias_correctas(self, candidato_data, proceso_data):
        mock_client = _mock_client(RESPUESTA_VALIDA)
        with patch.object(_gp_mod, "_get_client", return_value=mock_client):
            from agente_entrevistas.tools.generar_preguntas import generar_preguntas
            result = generar_preguntas(candidato_nombre=candidato_data["nombre"], skills=candidato_data["skills"], experiencia=candidato_data["experiencia"], cv_texto=None, jd_texto=None, info_publica=None)

        categorias = {p["categoria"] for p in result["preguntas"]}
        assert "técnica" in categorias
        assert "conductual" in categorias
        assert "presión" in categorias

    def test_sin_cv_ni_jd_no_explota(self, candidato_data):
        mock_client = _mock_client(RESPUESTA_VALIDA)
        with patch.object(_gp_mod, "_get_client", return_value=mock_client):
            from agente_entrevistas.tools.generar_preguntas import generar_preguntas
            result = generar_preguntas(candidato_nombre=candidato_data["nombre"], skills=[], experiencia=[], cv_texto=None, jd_texto=None, info_publica=None)

        assert "error" not in result

    def test_gemini_devuelve_json_invalido(self, candidato_data):
        mock_client = MagicMock()
        mock_client.messages.create.return_value.content = [MagicMock(text="Lo siento, no puedo generar preguntas.")]
        with patch.object(_gp_mod, "_get_client", return_value=mock_client):
            from agente_entrevistas.tools.generar_preguntas import generar_preguntas
            result = generar_preguntas(candidato_nombre=candidato_data["nombre"], skills=[], experiencia=[], cv_texto=None, jd_texto=None, info_publica=None)

        assert "error" in result

    def test_gemini_json_con_campos_faltantes(self, candidato_data):
        mock_client = _mock_client({"total": 1, "preguntas": [{"categoria": "técnica", "pregunta": "¿...?"}]})
        with patch.object(_gp_mod, "_get_client", return_value=mock_client):
            from agente_entrevistas.tools.generar_preguntas import generar_preguntas
            result = generar_preguntas(candidato_nombre=candidato_data["nombre"], skills=[], experiencia=[], cv_texto=None, jd_texto=None, info_publica=None)

        assert "error" in result

    def test_prompt_incluye_nombre_candidato(self, candidato_data):
        mock_client = _mock_client(RESPUESTA_VALIDA)
        with patch.object(_gp_mod, "_get_client", return_value=mock_client):
            from agente_entrevistas.tools.generar_preguntas import generar_preguntas
            generar_preguntas(candidato_nombre="NombreUnicoXYZ123", skills=[], experiencia=[], cv_texto=None, jd_texto=None, info_publica=None)

        prompt = mock_client.messages.create.call_args[1]["messages"][0]["content"]
        assert "NombreUnicoXYZ123" in prompt

    def test_prompt_incluye_skills(self, candidato_data):
        mock_client = _mock_client(RESPUESTA_VALIDA)
        with patch.object(_gp_mod, "_get_client", return_value=mock_client):
            from agente_entrevistas.tools.generar_preguntas import generar_preguntas
            generar_preguntas(candidato_nombre="Test", skills=["SkillRaroTest999"], experiencia=[], cv_texto=None, jd_texto=None, info_publica=None)

        prompt = mock_client.messages.create.call_args[1]["messages"][0]["content"]
        assert "SkillRaroTest999" in prompt
