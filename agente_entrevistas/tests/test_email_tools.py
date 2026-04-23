"""
Tests para tools/crear_borrador_email.py y tools/redactar_email.py
"""
 
import os
import pytest
from unittest.mock import patch, MagicMock
 
os.environ.setdefault("ANTHROPIC_API_KEY",   "test-anthropic-key")
os.environ.setdefault("MS_SENDER_EMAIL",     "rrhh@empresa.com")
os.environ.setdefault("MAILTRAP_API_TOKEN",  "test-mailtrap-token")
 
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
 
 
@pytest.fixture
def mock_mailtrap():
    """Mock del cliente Mailtrap para no hacer llamadas reales."""
    mock_client   = MagicMock()
    mock_response = MagicMock()
    mock_client.send.return_value = mock_response
 
    with patch("agente_entrevistas.tools.crear_borrador_email.mt.MailtrapClient",
               return_value=mock_client) as mock_class:
        yield mock_client
 
 
@pytest.fixture
def mock_claude_email():
    """Mock del cliente Anthropic para redactar_email."""
    mock_client = MagicMock()
    mock_msg    = MagicMock()
    mock_msg.content = [MagicMock(text=(
        "Estimada Martina,\n\n"
        "Me comunico con vos porque tu perfil en Python y FastAPI es muy relevante "
        "para una oportunidad que tenemos abierta como Senior Backend Engineer.\n\n"
        "Se trata de un rol desafiante en el sector fintech. Si te interesa saber mas, "
        "no dudes en responder este email.\n\n"
        "El equipo de Talent Acquisition"
    ))]
    mock_client.messages.create.return_value = mock_msg
    with patch.object(_re_mod, "_get_client", return_value=mock_client):
        yield mock_client
 
 
class TestCrearBorradorEmail:
 
    def test_retorna_status_enviado(self, candidato, mock_mailtrap):
        from agente_entrevistas.tools.crear_borrador_email import crear_borrador_email
        result = crear_borrador_email(
            candidato_nombre=candidato["nombre"],
            candidato_email=candidato["email"],
            proceso_titulo=candidato["proceso_titulo"],
            cuerpo_email="Hola Martina, te contactamos por una oportunidad.",
        )
        assert result["status"] == "enviado"
 
    def test_usa_sender_del_env_por_defecto(self, candidato, mock_mailtrap):
        from agente_entrevistas.tools.crear_borrador_email import crear_borrador_email
        result = crear_borrador_email(
            candidato_nombre=candidato["nombre"],
            candidato_email=candidato["email"],
            proceso_titulo=candidato["proceso_titulo"],
            cuerpo_email="Cuerpo",
        )
        assert result["remitente"] == "rrhh@empresa.com"
 
    def test_usa_remitente_custom(self, candidato, mock_mailtrap):
        from agente_entrevistas.tools.crear_borrador_email import crear_borrador_email
        result = crear_borrador_email(
            candidato_nombre=candidato["nombre"],
            candidato_email=candidato["email"],
            proceso_titulo=candidato["proceso_titulo"],
            cuerpo_email="Cuerpo",
            remitente_email="recruiting@otra.com",
        )
        assert result["remitente"] == "recruiting@otra.com"
 
    def test_asunto_autogenerado(self, candidato, mock_mailtrap):
        from agente_entrevistas.tools.crear_borrador_email import crear_borrador_email
        result = crear_borrador_email(
            candidato_nombre=candidato["nombre"],
            candidato_email=candidato["email"],
            proceso_titulo=candidato["proceso_titulo"],
            cuerpo_email="Cuerpo",
        )
        assert candidato["proceso_titulo"] in result["asunto"]
 
    def test_asunto_custom(self, candidato, mock_mailtrap):
        from agente_entrevistas.tools.crear_borrador_email import crear_borrador_email
        result = crear_borrador_email(
            candidato_nombre=candidato["nombre"],
            candidato_email=candidato["email"],
            proceso_titulo=candidato["proceso_titulo"],
            cuerpo_email="Cuerpo",
            asunto="Asunto personalizado test",
        )
        assert result["asunto"] == "Asunto personalizado test"
 
    def test_destinatario_en_retorno(self, candidato, mock_mailtrap):
        from agente_entrevistas.tools.crear_borrador_email import crear_borrador_email
        result = crear_borrador_email(
            candidato_nombre=candidato["nombre"],
            candidato_email=candidato["email"],
            proceso_titulo=candidato["proceso_titulo"],
            cuerpo_email="Cuerpo",
        )
        assert result["destinatario"] == candidato["email"]
 
    def test_client_send_llamado(self, candidato, mock_mailtrap):
        from agente_entrevistas.tools.crear_borrador_email import crear_borrador_email
        crear_borrador_email(
            candidato_nombre=candidato["nombre"],
            candidato_email=candidato["email"],
            proceso_titulo=candidato["proceso_titulo"],
            cuerpo_email="Cuerpo",
        )
        mock_mailtrap.send.assert_called_once()
 
    def test_sin_api_token_retorna_error(self, candidato):
        with patch.dict(os.environ, {"MAILTRAP_API_TOKEN": ""}):
            from agente_entrevistas.tools.crear_borrador_email import crear_borrador_email
            result = crear_borrador_email(
                candidato_nombre=candidato["nombre"],
                candidato_email=candidato["email"],
                proceso_titulo=candidato["proceso_titulo"],
                cuerpo_email="Cuerpo",
            )
        assert "error" in result
 
    def test_error_mailtrap_retorna_error(self, candidato):
        with patch("agente_entrevistas.tools.crear_borrador_email.mt.MailtrapClient",
                   side_effect=Exception("API error")):
            from agente_entrevistas.tools.crear_borrador_email import crear_borrador_email
            result = crear_borrador_email(
                candidato_nombre=candidato["nombre"],
                candidato_email=candidato["email"],
                proceso_titulo=candidato["proceso_titulo"],
                cuerpo_email="Cuerpo",
            )
        assert "error" in result
 
    def test_mensaje_confirma_envio(self, candidato, mock_mailtrap):
        from agente_entrevistas.tools.crear_borrador_email import crear_borrador_email
        result = crear_borrador_email(
            candidato_nombre=candidato["nombre"],
            candidato_email=candidato["email"],
            proceso_titulo=candidato["proceso_titulo"],
            cuerpo_email="Cuerpo",
        )
        assert candidato["email"] in result["mensaje"]
 
    def test_cuerpo_html_detectado(self, candidato, mock_mailtrap):
        """Si el cuerpo empieza con <, debe enviarse como HTML."""
        with patch("agente_entrevistas.tools.crear_borrador_email.mt.Mail") as mock_mail:
            mock_mail.return_value = MagicMock()
            from agente_entrevistas.tools.crear_borrador_email import crear_borrador_email
            crear_borrador_email(
                candidato_nombre=candidato["nombre"],
                candidato_email=candidato["email"],
                proceso_titulo=candidato["proceso_titulo"],
                cuerpo_email="<p>Hola Martina</p>",
            )
        call_kwargs = mock_mail.call_args[1]
        assert call_kwargs.get("html") is not None
        assert call_kwargs.get("text") is None
 
    def test_cuerpo_texto_detectado(self, candidato, mock_mailtrap):
        """Si el cuerpo es texto plano, debe enviarse como text."""
        with patch("agente_entrevistas.tools.crear_borrador_email.mt.Mail") as mock_mail:
            mock_mail.return_value = MagicMock()
            from agente_entrevistas.tools.crear_borrador_email import crear_borrador_email
            crear_borrador_email(
                candidato_nombre=candidato["nombre"],
                candidato_email=candidato["email"],
                proceso_titulo=candidato["proceso_titulo"],
                cuerpo_email="Hola Martina, texto plano.",
            )
        call_kwargs = mock_mail.call_args[1]
        assert call_kwargs.get("text") is not None
        assert call_kwargs.get("html") is None
 
 
class TestRedactarEmail:
 
    def test_retorna_cuerpo_texto(self, candidato, mock_claude_email):
        from agente_entrevistas.tools.redactar_email import redactar_email
        result = redactar_email(
            candidato_nombre=candidato["nombre"],
            proceso_titulo=candidato["proceso_titulo"],
            skills_clave=candidato["skills_clave"],
        )
        assert "error" not in result
        assert len(result["cuerpo_texto"]) > 50
 
    def test_retorna_cuerpo_html(self, candidato, mock_claude_email):
        from agente_entrevistas.tools.redactar_email import redactar_email
        result = redactar_email(
            candidato_nombre=candidato["nombre"],
            proceso_titulo=candidato["proceso_titulo"],
            skills_clave=candidato["skills_clave"],
        )
        assert "<p>" in result["cuerpo_html"]
 
    def test_retorna_asunto(self, candidato, mock_claude_email):
        from agente_entrevistas.tools.redactar_email import redactar_email
        result = redactar_email(
            candidato_nombre=candidato["nombre"],
            proceso_titulo=candidato["proceso_titulo"],
            skills_clave=candidato["skills_clave"],
        )
        assert candidato["proceso_titulo"] in result["asunto"]
 
    def test_prompt_incluye_nombre_candidato(self, candidato, mock_claude_email):
        from agente_entrevistas.tools.redactar_email import redactar_email
        redactar_email(
            candidato_nombre="NombreUnicoXYZ",
            proceso_titulo=candidato["proceso_titulo"],
            skills_clave=candidato["skills_clave"],
        )
        prompt = mock_claude_email.messages.create.call_args[1]["messages"][0]["content"]
        assert "NombreUnicoXYZ" in prompt
 
    def test_prompt_incluye_skills(self, candidato, mock_claude_email):
        from agente_entrevistas.tools.redactar_email import redactar_email
        redactar_email(
            candidato_nombre=candidato["nombre"],
            proceso_titulo=candidato["proceso_titulo"],
            skills_clave=["SkillRaroTest999"],
        )
        prompt = mock_claude_email.messages.create.call_args[1]["messages"][0]["content"]
        assert "SkillRaroTest999" in prompt
 
    def test_max_4_skills_en_prompt(self, mock_claude_email):
        from agente_entrevistas.tools.redactar_email import redactar_email
        redactar_email(
            candidato_nombre="Test",
            proceso_titulo="Dev Role",
            skills_clave=["S1", "S2", "S3", "S4", "S5", "S6"],
        )
        prompt = mock_claude_email.messages.create.call_args[1]["messages"][0]["content"]
        assert "S5" not in prompt
        assert "S6" not in prompt
 
    def test_claude_falla_retorna_error(self, candidato):
        mock_client = MagicMock()
        mock_client.messages.create.side_effect = Exception("API down")
        with patch.object(_re_mod, "_get_client", return_value=mock_client):
            from agente_entrevistas.tools.redactar_email import redactar_email
            result = redactar_email(
                candidato_nombre=candidato["nombre"],
                proceso_titulo=candidato["proceso_titulo"],
                skills_clave=candidato["skills_clave"],
            )
        assert "error" in result
 
    def test_sin_empresa_no_explota(self, candidato, mock_claude_email):
        from agente_entrevistas.tools.redactar_email import redactar_email
        result = redactar_email(
            candidato_nombre=candidato["nombre"],
            proceso_titulo=candidato["proceso_titulo"],
            skills_clave=candidato["skills_clave"],
            empresa_nombre=None,
        )
        assert "error" not in result
 
    def test_idioma_ingles(self, candidato, mock_claude_email):
        from agente_entrevistas.tools.redactar_email import redactar_email
        redactar_email(
            candidato_nombre=candidato["nombre"],
            proceso_titulo=candidato["proceso_titulo"],
            skills_clave=candidato["skills_clave"],
            idioma="inglés",
        )
        prompt = mock_claude_email.messages.create.call_args[1]["messages"][0]["content"]
        assert "inglés" in prompt