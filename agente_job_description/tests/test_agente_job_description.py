"""
Tests del Agente Job Description.

Estos tests cubren:
  - JobDescriptionEstructurada: verifica que el schema valide correctamente los datos
    que el LLM está obligado a devolver (output_schema). Es el análogo de TestConsultarATS
    en busquedas_internas: testea el contrato de salida sin ejecutar el LLM.
  - Estructura del agente ADK: verifica que root_agent esté bien configurado.

No requieren conexión a APIs externas (no se ejecuta el LLM).
"""
import sys
import os
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from schemas.JobDescriptionEstructurada import JobDescriptionEstructurada


JD_EJEMPLO_DICT = {
    "role_title": "Senior Python Developer",
    "role_description": (
        "Liderá el desarrollo de microservicios en Python para la plataforma de pagos. "
        "Trabajará con el equipo de backend para diseñar APIs RESTful escalables."
    ),
    "management_level": "Individual Contributor",
    "skills": ["Python", "FastAPI", "Docker", "AWS", "comunicación efectiva"],
}


# ---------------------------------------------------------------------------
# Tests: JobDescriptionEstructurada (schema de salida del agente)
# ---------------------------------------------------------------------------
class TestJobDescriptionEstructurada(unittest.TestCase):
    """
    Tests del schema que el agente debe producir.

    El agente job_description no tiene tools: el LLM parsea la JD directamente
    y está forzado por output_schema a devolver un JobDescriptionEstructurada válido.
    Estos tests verifican que el schema acepta datos correctos y rechaza datos
    incompletos, sin necesidad de llamar al LLM.
    """

    def test_instancia_valida_acepta_campos_completos(self):
        jd = JobDescriptionEstructurada(**JD_EJEMPLO_DICT)
        self.assertEqual(jd.role_title, "Senior Python Developer")
        self.assertEqual(jd.management_level, "Individual Contributor")
        self.assertEqual(len(jd.skills), 5)

    def test_serializa_a_dict_con_todos_los_campos(self):
        jd = JobDescriptionEstructurada(**JD_EJEMPLO_DICT)
        d = jd.model_dump()
        self.assertIn("role_title", d)
        self.assertIn("role_description", d)
        self.assertIn("management_level", d)
        self.assertIn("skills", d)

    def test_skills_puede_ser_lista_vacia(self):
        datos = {**JD_EJEMPLO_DICT, "skills": []}
        jd = JobDescriptionEstructurada(**datos)
        self.assertEqual(jd.skills, [])

    def test_skills_preserva_todos_los_elementos(self):
        jd = JobDescriptionEstructurada(**JD_EJEMPLO_DICT)
        self.assertIn("Python", jd.skills)
        self.assertIn("comunicación efectiva", jd.skills)

    def test_management_level_acepta_todos_los_niveles_validos(self):
        niveles = [
            "Individual Contributor",
            "Team Lead",
            "Manager",
            "Senior Manager",
            "Director",
            "Vice President",
        ]
        for nivel in niveles:
            datos = {**JD_EJEMPLO_DICT, "management_level": nivel}
            jd = JobDescriptionEstructurada(**datos)
            self.assertEqual(jd.management_level, nivel)

    def test_requiere_role_title(self):
        from pydantic import ValidationError
        datos = {k: v for k, v in JD_EJEMPLO_DICT.items() if k != "role_title"}
        with self.assertRaises(ValidationError):
            JobDescriptionEstructurada(**datos)

    def test_requiere_role_description(self):
        from pydantic import ValidationError
        datos = {k: v for k, v in JD_EJEMPLO_DICT.items() if k != "role_description"}
        with self.assertRaises(ValidationError):
            JobDescriptionEstructurada(**datos)

    def test_requiere_management_level(self):
        from pydantic import ValidationError
        datos = {k: v for k, v in JD_EJEMPLO_DICT.items() if k != "management_level"}
        with self.assertRaises(ValidationError):
            JobDescriptionEstructurada(**datos)

    def test_requiere_skills(self):
        from pydantic import ValidationError
        datos = {k: v for k, v in JD_EJEMPLO_DICT.items() if k != "skills"}
        with self.assertRaises(ValidationError):
            JobDescriptionEstructurada(**datos)


# ---------------------------------------------------------------------------
# Tests: estructura del agente ADK
# ---------------------------------------------------------------------------
class TestAgenteJobDescriptionEstructura(unittest.TestCase):
    """
    Verifica que el agente ADK esté configurado correctamente.

    Estos tests no ejecutan el LLM: solo verifican que root_agent exista,
    no tenga tools (parsea la JD directamente sin delegar a funciones externas)
    y use el output_schema esperado.
    """

    def test_root_agent_existe(self):
        from agentes.job_description import agent
        self.assertTrue(hasattr(agent, "root_agent"), "agent.py debe exportar `root_agent`")

    def test_root_agent_no_tiene_tools(self):
        from agentes.job_description.agent import root_agent
        self.assertFalse(root_agent.tools)

    def test_root_agent_output_schema_es_job_description_estructurada(self):
        from agentes.job_description.agent import root_agent
        from schemas import JobDescriptionEstructurada as JDE
        self.assertIs(root_agent.output_schema, JDE)

    def test_root_agent_tiene_nombre_correcto(self):
        from agentes.job_description.agent import root_agent
        self.assertEqual(root_agent.name, "job_description")


if __name__ == "__main__":
    unittest.main()
