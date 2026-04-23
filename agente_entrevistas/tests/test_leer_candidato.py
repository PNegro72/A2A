import pytest
from unittest.mock import MagicMock
import agente_entrevistas.tools.leer_candidato as _lc_mod


def _make_supabase_mock(candidato_row=None, proceso_row=None):
    mock_client = MagicMock()
    candidato_resp = MagicMock()
    candidato_resp.data = candidato_row
    proceso_resp = MagicMock()
    proceso_resp.data = proceso_row

    def table_side_effect(table_name):
        t = MagicMock()
        t.select.return_value = t
        t.eq.return_value = t
        t.single.return_value = t
        t.execute.return_value = candidato_resp if table_name == "candidatos" else proceso_resp
        return t

    mock_client.table.side_effect = table_side_effect
    return mock_client


class TestLeerCandidato:

    def test_retorna_perfil_completo(self, candidato_data, proceso_data):
        raw_candidato = {
            "id": candidato_data["candidato_id"], "nombre": candidato_data["nombre"],
            "email": candidato_data["email"], "linkedin_url": candidato_data["linkedin_url"],
            "github_username": candidato_data["github_username"],
            "skills": candidato_data["skills"], "experiencia": candidato_data["experiencia"],
            "cv_texto": candidato_data["cv_texto"],
        }
        mock_sb = _make_supabase_mock(raw_candidato, {"titulo": proceso_data["titulo"], "jd_texto": proceso_data["jd_texto"]})

        from unittest.mock import patch
        with patch.object(_lc_mod, "create_client", return_value=mock_sb):
            from agente_entrevistas.tools.leer_candidato import leer_candidato
            result = leer_candidato(candidato_id=candidato_data["candidato_id"], proceso_id=proceso_data["proceso_id"])

        assert result["nombre"] == "Martina Rodríguez"
        assert "Python" in result["skills"]
        assert len(result["experiencia"]) == 2
        assert result["jd_texto"] == proceso_data["jd_texto"]
        assert "error" not in result

    def test_candidato_no_encontrado(self, proceso_data):
        mock_sb = _make_supabase_mock(candidato_row=None, proceso_row=None)

        from unittest.mock import patch
        with patch.object(_lc_mod, "create_client", return_value=mock_sb):
            from agente_entrevistas.tools.leer_candidato import leer_candidato
            result = leer_candidato(candidato_id="uuid-inexistente", proceso_id=proceso_data["proceso_id"])

        assert "error" in result

    def test_proceso_sin_jd(self, candidato_data):
        raw_candidato = {
            "id": candidato_data["candidato_id"], "nombre": candidato_data["nombre"],
            "email": None, "linkedin_url": None, "github_username": None,
            "skills": [], "experiencia": [], "cv_texto": None,
        }
        mock_sb = _make_supabase_mock(raw_candidato, {"titulo": "Backend Role", "jd_texto": None})

        from unittest.mock import patch
        with patch.object(_lc_mod, "create_client", return_value=mock_sb):
            from agente_entrevistas.tools.leer_candidato import leer_candidato
            result = leer_candidato(candidato_id=candidato_data["candidato_id"], proceso_id="uuid-sin-jd")

        assert result["jd_texto"] is None
        assert "error" not in result

    def test_candidato_sin_experiencia(self, candidato_data, proceso_data):
        raw_candidato = {
            "id": candidato_data["candidato_id"], "nombre": candidato_data["nombre"],
            "email": None, "linkedin_url": None, "github_username": None,
            "skills": ["Python"], "experiencia": [], "cv_texto": None,
        }
        mock_sb = _make_supabase_mock(raw_candidato, {"titulo": "Dev", "jd_texto": None})

        from unittest.mock import patch
        with patch.object(_lc_mod, "create_client", return_value=mock_sb):
            from agente_entrevistas.tools.leer_candidato import leer_candidato
            result = leer_candidato(candidato_id=candidato_data["candidato_id"], proceso_id=proceso_data["proceso_id"])

        assert result["experiencia"] == []
        assert result["skills"] == ["Python"]
