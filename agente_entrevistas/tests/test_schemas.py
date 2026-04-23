import pytest
from pydantic import ValidationError
from agente_entrevistas.models.schemas import (
    Candidato, ExperienciaLaboral, EntrevistaInput,
    Pregunta, PreguntasOutput, KitEntrevistaOutput,
)


class TestExperienciaLaboral:
    def test_minimo_valido(self):
        exp = ExperienciaLaboral(empresa="Acme", cargo="Dev")
        assert exp.empresa == "Acme"
        assert exp.desde is None

    def test_completo(self):
        exp = ExperienciaLaboral(empresa="MP", cargo="Sr.", desde="2021-03", hasta=None, descripcion="Pagos")
        assert exp.hasta is None

    def test_falta_campo_requerido(self):
        with pytest.raises(ValidationError):
            ExperienciaLaboral(empresa="Acme")


class TestCandidato:
    def test_minimo_valido(self):
        c = Candidato(candidato_id="uuid-001", nombre="Juan")
        assert c.skills == []

    def test_completo(self, candidato_data):
        exp_list = [ExperienciaLaboral(**e) for e in candidato_data["experiencia"]]
        c = Candidato(candidato_id=candidato_data["candidato_id"], nombre=candidato_data["nombre"], skills=candidato_data["skills"], experiencia=exp_list)
        assert len(c.skills) == 7
        assert c.experiencia[0].empresa == "Mercado Pago"

    def test_serializa_a_dict(self):
        c = Candidato(candidato_id="uuid-001", nombre="Test")
        d = c.model_dump()
        assert isinstance(d, dict)
        assert d["skills"] == []


class TestEntrevistaInput:
    def test_valido_con_jd(self):
        ei = EntrevistaInput(candidato_id="uuid-001", proceso_id="uuid-proc-001", jd_texto="JD...")
        assert ei.jd_texto is not None

    def test_valido_sin_jd(self):
        ei = EntrevistaInput(candidato_id="uuid-001", proceso_id="uuid-proc-001")
        assert ei.jd_texto is None

    def test_falta_proceso_id(self):
        with pytest.raises(ValidationError):
            EntrevistaInput(candidato_id="uuid-001")


class TestPregunta:
    def test_valido(self):
        p = Pregunta(categoria="técnica", pregunta="¿...?", objetivo="Evaluar", nivel="senior")
        assert p.tiempo_estimado_min == 3

    def test_tiempo_custom(self):
        p = Pregunta(categoria="presión", pregunta="¿...?", objetivo="Detectar", nivel="senior", tiempo_estimado_min=8)
        assert p.tiempo_estimado_min == 8

    def test_falta_objetivo(self):
        with pytest.raises(ValidationError):
            Pregunta(categoria="técnica", pregunta="¿...?", nivel="senior")


class TestPreguntasOutput:
    def test_valido(self, preguntas_data):
        po = PreguntasOutput(total=len(preguntas_data), preguntas=[Pregunta(**p) for p in preguntas_data], duracion_estimada_min=40)
        assert po.total == 3

    def test_serializa(self, preguntas_data):
        po = PreguntasOutput(total=1, preguntas=[Pregunta(**preguntas_data[0])], duracion_estimada_min=8)
        d = po.model_dump()
        assert d["preguntas"][0]["categoria"] == "técnica"


class TestKitEntrevistaOutput:
    def test_valido_sin_pdf(self):
        kit = KitEntrevistaOutput(candidato_nombre="Martina", proceso_id="uuid-001", kit_path_docx="/output/kit.docx", preguntas_total=11, guardado_en_supabase=True)
        assert kit.kit_path_pdf is None

    def test_valido_con_pdf(self):
        kit = KitEntrevistaOutput(candidato_nombre="Martina", proceso_id="uuid-001", kit_path_docx="/output/kit.docx", kit_path_pdf="/output/kit.pdf", preguntas_total=11, guardado_en_supabase=False)
        assert kit.kit_path_pdf is not None
