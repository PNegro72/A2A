"""
Tests del Agente Búsquedas Internas y sus herramientas.

Estos tests cubren:
  - consultar_ats: verifica que la búsqueda semántica retorne datos bien formados.
  - Estructura del agente ADK: verifica que root_agent esté bien configurado.

No requieren conexión a APIs externas.

Nota: los tests de rankear_candidatos fueron eliminados porque esa tool ya no
existe. El ranking es responsabilidad del LlmAgent directamente (output_schema).
La persistencia en Supabase es responsabilidad del orquestador.
"""
import sys
import os
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from agentes.busquedas_internas.tools.consultar_ats import Consultar_ats
from schemas.JobDescriptionEstructurada import JobDescriptionEstructurada


JD_EJEMPLO = JobDescriptionEstructurada(
    role_title="Senior Python Developer",
    role_description=(
        "Buscamos un Senior Python Developer con experiencia en Machine Learning y AWS. "
        "Trabajará con el equipo de backend para diseñar APIs RESTful escalables."
    ),
    management_level="Individual Contributor",
    skills=["Python", "FastAPI", "Docker", "AWS", "Machine Learning"],
)


# ---------------------------------------------------------------------------
# Tests: consultar_ats
# ---------------------------------------------------------------------------
class TestConsultarATS(unittest.TestCase):
    """Tests del stub de consulta al ATS (Workday)."""

    def test_retorna_estructura_correcta(self):
        resultado = Consultar_ats(JD_EJEMPLO)
        self.assertIn("exito", resultado)
        self.assertIn("candidatos", resultado)
        self.assertIn("total", resultado)
        self.assertIn("mensaje", resultado)

    def test_exito_es_true_en_mock(self):
        resultado = Consultar_ats(JD_EJEMPLO)
        self.assertTrue(resultado["exito"])

    def test_total_coincide_con_longitud_de_lista(self):
        resultado = Consultar_ats(JD_EJEMPLO)
        self.assertEqual(resultado["total"], len(resultado["candidatos"]))

    def test_candidatos_tienen_campos_requeridos(self):
        resultado = Consultar_ats(JD_EJEMPLO)
        campos_requeridos = ["id", "nombre", "texto_cv", "score_embedding"]
        for candidato in resultado["candidatos"]:
            for campo in campos_requeridos:
                self.assertIn(
                    campo, candidato,
                    f"Campo '{campo}' faltante en candidato {candidato.get('id', '?')}"
                )

    def test_score_embedding_es_float_entre_0_y_1(self):
        resultado = Consultar_ats(JD_EJEMPLO)
        for candidato in resultado["candidatos"]:
            self.assertIsInstance(candidato["score_embedding"], float)
            self.assertGreaterEqual(candidato["score_embedding"], 0.0)
            self.assertLessEqual(candidato["score_embedding"], 1.0)

    def test_texto_cv_no_esta_vacio(self):
        resultado = Consultar_ats(JD_EJEMPLO)
        for candidato in resultado["candidatos"]:
            self.assertGreater(len(candidato["texto_cv"]), 0)


# ---------------------------------------------------------------------------
# Tests: estructura del agente ADK
# ---------------------------------------------------------------------------
class TestAgenteBusquedasInternasEstructura(unittest.TestCase):
    """
    Verifica que el agente ADK esté configurado correctamente.

    Estos tests no ejecutan el LLM: solo verifican que root_agent exista,
    tenga las tools correctas y use el output_schema esperado.
    """

    def test_root_agent_existe(self):
        from agentes.busquedas_internas import agent
        self.assertTrue(hasattr(agent, "root_agent"), "agent.py debe exportar `root_agent`")

    def test_root_agent_tiene_una_tool(self):
        from agentes.busquedas_internas.agent import root_agent
        self.assertEqual(len(root_agent.tools), 1)

    def test_root_agent_output_schema_es_resultado_ranking(self):
        from agentes.busquedas_internas.agent import root_agent
        from schemas import ResultadoRanking
        self.assertIs(root_agent.output_schema, ResultadoRanking)

    def test_root_agent_tiene_nombre_correcto(self):
        from agentes.busquedas_internas.agent import root_agent
        self.assertEqual(root_agent.name, "busquedas_internas")


if __name__ == "__main__":
    unittest.main()
