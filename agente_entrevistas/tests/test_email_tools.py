"""
Tests para tools/crear_borrador_email.py y tools/redactar_email.py

crear_borrador_email.py ya no envía el email directamente (eso vivía antes en
Mailtrap): delega el envío real al agente de scheduling vía HTTP
(POST SCHEDULING_AGENT_URL, action=send_email). Estos tests mockean esa
llamada HTTP y verifican cómo crear_borrador_email interpreta la respuesta.
"""

import os
import pytest
from unittest.mock import patch, MagicMock

os.environ.setdefault("OPENAI_API_KEY",  "test-openai-key")
os.environ.setdefault("MS_SENDER_EMAIL", "rrhh@empresa.com")

import agente_entrevistas.tools.crear_borrador_email as _cbe_mod
import agente_entrevistas.tools.redactar_email as _re_mod


@pytest.fixture
def candidato():
    return {
        "nombre":         "Martina Rodríguez",
        "email":          "martina@gmail.com",
        "proceso_titulo": "Senior Backend Engineer – Fintech",
        "skills_clave":   ["Python", "FastAPI", "Kafka"],
    }


def _mock_response(status_code=200, json_body=None):
    """Construye un mock de requests.Response para el POST al scheduling agent."""
    response = MagicMock()
    response.status_code = status_code
    response.content = b"{}" if json_body is None else b"non-empty"
    response.json.return_value = json_body if json_body is not None else {}
    return response


@pytest.fixture
def mock_scheduling_ok():
    """Mock de requests.post: el scheduling agent confirma el envío."""
    response = _mock_response(200, {
        "status": "enviado",
        "message_id": "msg-123",
        "remitente": "rrhh@empresa.com",
        "mensaje": "Email enviado correctamente a martina@gmail.com via Gmail (rrhh@empresa.com).",
    })
    with patch.object(_cbe_mod.requests, "post", return_value=response) as mock_post:
        yield mock_post


@pytest.fixture
def mock_openai_email():
    """Mock del cliente OpenAI para redactar_email."""
    mock_client = MagicMock()
    mock_resp   = MagicMock()
    mock_resp.choices = [MagicMock(message=MagicMock(content=(
        "Estimada Martina,\n\n"
        "Me comunico con vos porque tu perfil en Python y FastAPI es muy relevante "
        "para una oportunidad que tenemos abierta como Senior Backend Engineer.\n\n"
        "Se trata de un rol desafiante en el sector fintech. Si te interesa saber mas, "
        "no dudes en responder este email.\n\n"
        "El equipo de Talent Acquisition"
    )))]
    mock_client.chat.completions.create.return_value = mock_resp
    with patch.object(_re_mod, "_get_client", return_value=mock_client):
        yield mock_client


class TestCrearBorradorEmail:

    def test_retorna_status_enviado(self, candidato, mock_scheduling_ok):
        from agente_entrevistas.tools.crear_borrador_email import crear_borrador_email
        result = crear_borrador_email(
            candidato_nombre=candidato["nombre"],
            candidato_email=candidato["email"],
            proceso_titulo=candidato["proceso_titulo"],
            cuerpo_email="Hola Martina, te contactamos por una oportunidad.",
        )
        assert result["status"] == "enviado"

    def test_delega_al_agente_scheduling(self, candidato, mock_scheduling_ok):
        """El envío real se delega vía HTTP al scheduling agent, no se hace acá."""
        from agente_entrevistas.tools.crear_borrador_email import crear_borrador_email
        crear_borrador_email(
            candidato_nombre=candidato["nombre"],
            candidato_email=candidato["email"],
            proceso_titulo=candidato["proceso_titulo"],
            cuerpo_email="Cuerpo",
        )
        mock_scheduling_ok.assert_called_once()
        call_kwargs = mock_scheduling_ok.call_args
        payload = call_kwargs.kwargs["json"]
        assert payload["action"] == "send_email"
        assert payload["candidato_email"] == candidato["email"]
        assert call_kwargs.kwargs["timeout"] > 0

    def test_usa_url_del_env_si_esta_configurada(self, candidato, mock_scheduling_ok):
        from agente_entrevistas.tools.crear_borrador_email import crear_borrador_email
        with patch.dict(os.environ, {"SCHEDULING_AGENT_URL": "http://scheduling.internal/scheduling-agent"}):
            crear_borrador_email(
                candidato_nombre=candidato["nombre"],
                candidato_email=candidato["email"],
                proceso_titulo=candidato["proceso_titulo"],
                cuerpo_email="Cuerpo",
            )
        called_url = mock_scheduling_ok.call_args.args[0]
        assert called_url == "http://scheduling.internal/scheduling-agent"

    def test_usa_remitente_devuelto_por_scheduling(self, candidato, mock_scheduling_ok):
        """El remitente real lo decide el scheduling agent (cuenta Gmail autenticada)."""
        from agente_entrevistas.tools.crear_borrador_email import crear_borrador_email
        result = crear_borrador_email(
            candidato_nombre=candidato["nombre"],
            candidato_email=candidato["email"],
            proceso_titulo=candidato["proceso_titulo"],
            cuerpo_email="Cuerpo",
        )
        assert result["remitente"] == "rrhh@empresa.com"

    def test_usa_env_como_fallback_de_remitente(self, candidato):
        """Si el scheduling agent no informa remitente, cae al MS_SENDER_EMAIL configurado."""
        response = _mock_response(200, {"status": "enviado", "mensaje": "ok"})
        with patch.object(_cbe_mod.requests, "post", return_value=response):
            from agente_entrevistas.tools.crear_borrador_email import crear_borrador_email
            result = crear_borrador_email(
                candidato_nombre=candidato["nombre"],
                candidato_email=candidato["email"],
                proceso_titulo=candidato["proceso_titulo"],
                cuerpo_email="Cuerpo",
            )
        assert result["remitente"] == "rrhh@empresa.com"

    def test_asunto_autogenerado(self, candidato, mock_scheduling_ok):
        from agente_entrevistas.tools.crear_borrador_email import crear_borrador_email
        result = crear_borrador_email(
            candidato_nombre=candidato["nombre"],
            candidato_email=candidato["email"],
            proceso_titulo=candidato["proceso_titulo"],
            cuerpo_email="Cuerpo",
        )
        assert candidato["proceso_titulo"] in result["asunto"]

    def test_asunto_custom(self, candidato, mock_scheduling_ok):
        from agente_entrevistas.tools.crear_borrador_email import crear_borrador_email
        result = crear_borrador_email(
            candidato_nombre=candidato["nombre"],
            candidato_email=candidato["email"],
            proceso_titulo=candidato["proceso_titulo"],
            cuerpo_email="Cuerpo",
            asunto="Asunto personalizado test",
        )
        assert result["asunto"] == "Asunto personalizado test"

    def test_destinatario_en_retorno(self, candidato, mock_scheduling_ok):
        from agente_entrevistas.tools.crear_borrador_email import crear_borrador_email
        result = crear_borrador_email(
            candidato_nombre=candidato["nombre"],
            candidato_email=candidato["email"],
            proceso_titulo=candidato["proceso_titulo"],
            cuerpo_email="Cuerpo",
        )
        assert result["destinatario"] == candidato["email"]

    def test_mensaje_confirma_envio(self, candidato, mock_scheduling_ok):
        from agente_entrevistas.tools.crear_borrador_email import crear_borrador_email
        result = crear_borrador_email(
            candidato_nombre=candidato["nombre"],
            candidato_email=candidato["email"],
            proceso_titulo=candidato["proceso_titulo"],
            cuerpo_email="Cuerpo",
        )
        assert candidato["email"] in result["mensaje"]

    def test_mensaje_del_scheduling_sin_email_lo_completa(self, candidato):
        """Si el mensaje del scheduling agent no menciona el email, se lo antepone."""
        response = _mock_response(200, {"status": "enviado", "mensaje": "Listo."})
        with patch.object(_cbe_mod.requests, "post", return_value=response):
            from agente_entrevistas.tools.crear_borrador_email import crear_borrador_email
            result = crear_borrador_email(
                candidato_nombre=candidato["nombre"],
                candidato_email=candidato["email"],
                proceso_titulo=candidato["proceso_titulo"],
                cuerpo_email="Cuerpo",
            )
        assert candidato["email"] in result["mensaje"]
        assert "Listo." in result["mensaje"]

    def test_email_enviado_flag_alternativo(self, candidato):
        """El scheduling agent puede confirmar con email_enviado=True en vez de status."""
        response = _mock_response(200, {"email_enviado": True})
        with patch.object(_cbe_mod.requests, "post", return_value=response):
            from agente_entrevistas.tools.crear_borrador_email import crear_borrador_email
            result = crear_borrador_email(
                candidato_nombre=candidato["nombre"],
                candidato_email=candidato["email"],
                proceso_titulo=candidato["proceso_titulo"],
                cuerpo_email="Cuerpo",
            )
        assert result["status"] == "enviado"

    def test_excepcion_de_red_retorna_error(self, candidato):
        with patch.object(_cbe_mod.requests, "post", side_effect=ConnectionError("no conecta")):
            from agente_entrevistas.tools.crear_borrador_email import crear_borrador_email
            result = crear_borrador_email(
                candidato_nombre=candidato["nombre"],
                candidato_email=candidato["email"],
                proceso_titulo=candidato["proceso_titulo"],
                cuerpo_email="Cuerpo",
            )
        assert "error" in result
        assert result["draft_id"] is None

    def test_status_code_error_retorna_error(self, candidato):
        response = _mock_response(500, {"message": "Gmail API caída"})
        with patch.object(_cbe_mod.requests, "post", return_value=response):
            from agente_entrevistas.tools.crear_borrador_email import crear_borrador_email
            result = crear_borrador_email(
                candidato_nombre=candidato["nombre"],
                candidato_email=candidato["email"],
                proceso_titulo=candidato["proceso_titulo"],
                cuerpo_email="Cuerpo",
            )
        assert result["error"] == "Gmail API caída"

    def test_scheduling_rechaza_envio_retorna_error(self, candidato):
        """status 200 pero el scheduling agent no confirma el envío (status distinto de enviado/ok)."""
        response = _mock_response(200, {"status": "error", "message": "Payload inválido"})
        with patch.object(_cbe_mod.requests, "post", return_value=response):
            from agente_entrevistas.tools.crear_borrador_email import crear_borrador_email
            result = crear_borrador_email(
                candidato_nombre=candidato["nombre"],
                candidato_email=candidato["email"],
                proceso_titulo=candidato["proceso_titulo"],
                cuerpo_email="Cuerpo",
            )
        assert result["error"] == "Payload inválido"


class TestRedactarEmail:

    def test_retorna_cuerpo_texto(self, candidato, mock_openai_email):
        from agente_entrevistas.tools.redactar_email import redactar_email
        result = redactar_email(
            candidato_nombre=candidato["nombre"],
            proceso_titulo=candidato["proceso_titulo"],
            skills_clave=candidato["skills_clave"],
        )
        assert "error" not in result
        assert len(result["cuerpo_texto"]) > 50

    def test_retorna_cuerpo_html(self, candidato, mock_openai_email):
        from agente_entrevistas.tools.redactar_email import redactar_email
        result = redactar_email(
            candidato_nombre=candidato["nombre"],
            proceso_titulo=candidato["proceso_titulo"],
            skills_clave=candidato["skills_clave"],
        )
        assert "<p>" in result["cuerpo_html"]

    def test_retorna_asunto(self, candidato, mock_openai_email):
        from agente_entrevistas.tools.redactar_email import redactar_email
        result = redactar_email(
            candidato_nombre=candidato["nombre"],
            proceso_titulo=candidato["proceso_titulo"],
            skills_clave=candidato["skills_clave"],
        )
        assert candidato["proceso_titulo"] in result["asunto"]

    def test_prompt_incluye_nombre_candidato(self, candidato, mock_openai_email):
        from agente_entrevistas.tools.redactar_email import redactar_email
        redactar_email(
            candidato_nombre="NombreUnicoXYZ",
            proceso_titulo=candidato["proceso_titulo"],
            skills_clave=candidato["skills_clave"],
        )
        prompt = mock_openai_email.chat.completions.create.call_args[1]["messages"][0]["content"]
        assert "NombreUnicoXYZ" in prompt

    def test_prompt_incluye_skills(self, candidato, mock_openai_email):
        from agente_entrevistas.tools.redactar_email import redactar_email
        redactar_email(
            candidato_nombre=candidato["nombre"],
            proceso_titulo=candidato["proceso_titulo"],
            skills_clave=["SkillRaroTest999"],
        )
        prompt = mock_openai_email.chat.completions.create.call_args[1]["messages"][0]["content"]
        assert "SkillRaroTest999" in prompt

    def test_max_4_skills_en_prompt(self, mock_openai_email):
        from agente_entrevistas.tools.redactar_email import redactar_email
        redactar_email(
            candidato_nombre="Test",
            proceso_titulo="Dev Role",
            skills_clave=["S1", "S2", "S3", "S4", "S5", "S6"],
        )
        prompt = mock_openai_email.chat.completions.create.call_args[1]["messages"][0]["content"]
        assert "S5" not in prompt
        assert "S6" not in prompt

    def test_openai_falla_retorna_error(self, candidato):
        mock_client = MagicMock()
        mock_client.chat.completions.create.side_effect = Exception("API down")
        with patch.object(_re_mod, "_get_client", return_value=mock_client):
            from agente_entrevistas.tools.redactar_email import redactar_email
            result = redactar_email(
                candidato_nombre=candidato["nombre"],
                proceso_titulo=candidato["proceso_titulo"],
                skills_clave=candidato["skills_clave"],
            )
        assert "error" in result

    def test_sin_empresa_no_explota(self, candidato, mock_openai_email):
        from agente_entrevistas.tools.redactar_email import redactar_email
        result = redactar_email(
            candidato_nombre=candidato["nombre"],
            proceso_titulo=candidato["proceso_titulo"],
            skills_clave=candidato["skills_clave"],
            empresa_nombre=None,
        )
        assert "error" not in result

    def test_idioma_ingles(self, candidato, mock_openai_email):
        from agente_entrevistas.tools.redactar_email import redactar_email
        redactar_email(
            candidato_nombre=candidato["nombre"],
            proceso_titulo=candidato["proceso_titulo"],
            skills_clave=candidato["skills_clave"],
            idioma="inglés",
        )
        prompt = mock_openai_email.chat.completions.create.call_args[1]["messages"][0]["content"]
        assert "inglés" in prompt
