import pytest
from unittest.mock import MagicMock
import agente_entrevistas.tools.guardar_resultado as _gr_mod


def _mock_supabase(return_data=None, raise_exc=None):
    mock_client = MagicMock()
    mock_exec   = MagicMock()
    if raise_exc:
        mock_exec.execute.side_effect = raise_exc
    else:
        mock_exec.execute.return_value = MagicMock(data=return_data or [{"id": "uuid-entrevista-001"}])
    mock_client.table.return_value.insert.return_value = mock_exec
    return mock_client


class TestGuardarResultado:

    def test_retorna_exito(self):
        mock_sb = _mock_supabase()
        from unittest.mock import patch
        with patch.object(_gr_mod, "create_client", return_value=mock_sb):
            from agente_entrevistas.tools.guardar_resultado import guardar_resultado
            result = guardar_resultado(candidato_id="uuid-001", proceso_id="uuid-proc-001", candidato_nombre="Martina", preguntas_total=11, kit_path_docx="/output/kit.docx")
        assert result["estado"] == "éxito"
        assert result["guardado_en_supabase"] is True

    def test_retorna_entrevista_id(self):
        mock_sb = _mock_supabase(return_data=[{"id": "uuid-entrevista-999"}])
        from unittest.mock import patch
        with patch.object(_gr_mod, "create_client", return_value=mock_sb):
            from agente_entrevistas.tools.guardar_resultado import guardar_resultado
            result = guardar_resultado(candidato_id="uuid-001", proceso_id="uuid-proc-001", candidato_nombre="Test", preguntas_total=5, kit_path_docx="/output/kit.docx")
        assert result["entrevista_id"] == "uuid-entrevista-999"

    def test_incluye_paths_en_retorno(self):
        mock_sb = _mock_supabase()
        from unittest.mock import patch
        with patch.object(_gr_mod, "create_client", return_value=mock_sb):
            from agente_entrevistas.tools.guardar_resultado import guardar_resultado
            result = guardar_resultado(candidato_id="uuid-001", proceso_id="uuid-proc-001", candidato_nombre="Test", preguntas_total=3, kit_path_docx="/output/kit.docx", kit_path_pdf="/output/kit.pdf")
        assert result["kit_path_docx"] == "/output/kit.docx"
        assert result["kit_path_pdf"]  == "/output/kit.pdf"

    def test_supabase_falla_retorna_advertencia(self):
        mock_sb = _mock_supabase(raise_exc=Exception("connection timeout"))
        from unittest.mock import patch
        with patch.object(_gr_mod, "create_client", return_value=mock_sb):
            from agente_entrevistas.tools.guardar_resultado import guardar_resultado
            result = guardar_resultado(candidato_id="uuid-001", proceso_id="uuid-proc-001", candidato_nombre="Test", preguntas_total=3, kit_path_docx="/output/kit.docx")
        assert result["estado"] == "éxito_con_advertencia"
        assert result["guardado_en_supabase"] is False
        assert "connection timeout" in result["advertencia"]

    def test_insert_recibe_campos_correctos(self):
        mock_sb = _mock_supabase()
        from unittest.mock import patch
        with patch.object(_gr_mod, "create_client", return_value=mock_sb):
            from agente_entrevistas.tools.guardar_resultado import guardar_resultado
            guardar_resultado(candidato_id="uuid-c", proceso_id="uuid-p", candidato_nombre="Juan Pérez", preguntas_total=8, kit_path_docx="/output/kit.docx", kit_path_pdf="/output/kit.pdf", duracion_estimada_min=60, notas="Perfil interesante")
        registro = mock_sb.table.return_value.insert.call_args[0][0]
        assert registro["candidato_id"] == "uuid-c"
        assert registro["preguntas_total"] == 8
        assert registro["estado"] == "kit_generado"
        assert registro["notas"] == "Perfil interesante"
        assert "generado_en" in registro

    def test_candidato_y_proceso_id_en_retorno(self):
        mock_sb = _mock_supabase()
        from unittest.mock import patch
        with patch.object(_gr_mod, "create_client", return_value=mock_sb):
            from agente_entrevistas.tools.guardar_resultado import guardar_resultado
            result = guardar_resultado(candidato_id="uuid-chequeo", proceso_id="uuid-proc", candidato_nombre="Test", preguntas_total=1, kit_path_docx="/output/kit.docx")
        assert result["candidato_id"] == "uuid-chequeo"
        assert result["proceso_id"]   == "uuid-proc"
