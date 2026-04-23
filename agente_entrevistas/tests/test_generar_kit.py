import zipfile
import pytest
from pathlib import Path


@pytest.fixture(autouse=True)
def output_dir(tmp_path, monkeypatch):
    monkeypatch.setenv("KIT_OUTPUT_DIR", str(tmp_path))
    return tmp_path


@pytest.fixture
def generar_kit_fn():
    from agente_entrevistas.tools.generar_kit import generar_kit
    return generar_kit


class TestGenerarKitIntegracion:

    def test_genera_archivo_docx(self, generar_kit_fn, kit_input):
        result = generar_kit_fn(**kit_input)
        assert "error" not in result, f"Error inesperado: {result.get('error')}"
        assert Path(result["kit_path_docx"]).exists()

    def test_archivo_tiene_tamaño_razonable(self, generar_kit_fn, kit_input):
        result = generar_kit_fn(**kit_input)
        size = Path(result["kit_path_docx"]).stat().st_size
        assert size > 5_000
        assert size < 5_000_000

    def test_es_zip_valido(self, generar_kit_fn, kit_input):
        result = generar_kit_fn(**kit_input)
        with zipfile.ZipFile(result["kit_path_docx"], "r") as z:
            nombres = z.namelist()
        assert "word/document.xml" in nombres
        assert "[Content_Types].xml" in nombres

    def test_xml_contiene_nombre_candidato(self, generar_kit_fn, kit_input):
        result = generar_kit_fn(**kit_input)
        with zipfile.ZipFile(result["kit_path_docx"]) as z:
            doc_xml = z.read("word/document.xml").decode("utf-8")
        assert "Martina" in doc_xml

    def test_xml_contiene_preguntas(self, generar_kit_fn, kit_input):
        result = generar_kit_fn(**kit_input)
        with zipfile.ZipFile(result["kit_path_docx"]) as z:
            doc_xml = z.read("word/document.xml").decode("utf-8")
        assert "idempotencia" in doc_xml
        assert "consumer group" in doc_xml

    def test_xml_contiene_skills(self, generar_kit_fn, kit_input):
        result = generar_kit_fn(**kit_input)
        with zipfile.ZipFile(result["kit_path_docx"]) as z:
            doc_xml = z.read("word/document.xml").decode("utf-8")
        assert "FastAPI" in doc_xml
        assert "Kafka" in doc_xml

    def test_nombre_archivo_incluye_candidato(self, generar_kit_fn, kit_input):
        result = generar_kit_fn(**kit_input)
        assert "martina" in Path(result["kit_path_docx"]).name.lower()
        assert result["kit_path_docx"].endswith(".docx")

    def test_preguntas_total_en_resultado(self, generar_kit_fn, kit_input):
        result = generar_kit_fn(**kit_input)
        assert result["preguntas_total"] == len(kit_input["preguntas"])

    def test_duracion_en_resultado(self, generar_kit_fn, kit_input):
        result = generar_kit_fn(**kit_input)
        assert result["duracion_estimada_min"] == 30

    def test_sin_preguntas_no_explota(self, generar_kit_fn, kit_input):
        kit = {**kit_input, "preguntas": [], "duracion_estimada_min": None}
        result = generar_kit_fn(**kit)
        assert "error" not in result
        assert Path(result["kit_path_docx"]).exists()

    def test_sin_experiencia_no_explota(self, generar_kit_fn, kit_input):
        result = generar_kit_fn(**{**kit_input, "experiencia": []})
        assert "error" not in result

    def test_sin_skills_no_explota(self, generar_kit_fn, kit_input):
        result = generar_kit_fn(**{**kit_input, "skills": []})
        assert "error" not in result

    def test_pdf_none_cuando_no_se_pide(self, generar_kit_fn, kit_input):
        result = generar_kit_fn(**kit_input, generar_pdf=False)
        assert result["kit_path_pdf"] is None

    def test_nombres_con_caracteres_especiales(self, generar_kit_fn, kit_input):
        result = generar_kit_fn(**{**kit_input, "candidato_nombre": "Ñoño García Ávila"})
        assert "error" not in result
        assert Path(result["kit_path_docx"]).exists()
