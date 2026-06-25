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
import asyncio
import sys
import os
import unittest
from unittest import mock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from agentes.busquedas_internas.tools.consultar_ats import (
    Consultar_ats,
    _agrupar_chunks_por_cv,
)
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

# Chunks falsos que imitan la respuesta de la tool `search` del MCP de RAGaaS.
# Dos documentos (CVs), uno partido en dos chunks, para ejercitar el agrupamiento.
FAKE_CHUNKS = [
    {
        "score": 0.81, "text": "Senior Python Developer. Experiencia en AWS.",
        "source_file": "Julian Monte.pptx", "chunk_index": 0, "section": "", "page": 1,
    },
    {
        "score": 0.74, "text": "Machine Learning, FastAPI, Docker.",
        "source_file": "Julian Monte.pptx", "chunk_index": 1, "section": "", "page": 1,
    },
    {
        "score": 0.62, "text": "Backend engineer, APIs RESTful escalables.",
        "source_file": "Ana Penacchioni.pptx", "chunk_index": 0, "section": "", "page": 1,
    },
]


def _consultar(jd, chunks=FAKE_CHUNKS):
    """Ejecuta la tool async con el cliente MCP mockeado (sin red)."""
    async_mock = mock.AsyncMock(return_value=list(chunks))
    with mock.patch(
        "agentes.busquedas_internas.tools.consultar_ats.buscar_chunks", async_mock
    ):
        return asyncio.run(Consultar_ats(jd))


# ---------------------------------------------------------------------------
# Tests: consultar_ats (MCP de RAGaaS mockeado)
# ---------------------------------------------------------------------------
class TestConsultarATS(unittest.TestCase):
    """Tests de la consulta al ATS vía MCP de RAGaaS (con el MCP mockeado)."""

    def test_retorna_estructura_correcta(self):
        resultado = _consultar(JD_EJEMPLO)
        self.assertIn("exito", resultado)
        self.assertIn("candidatos", resultado)
        self.assertIn("total", resultado)
        self.assertIn("mensaje", resultado)

    def test_exito_es_true_con_resultados(self):
        resultado = _consultar(JD_EJEMPLO)
        self.assertTrue(resultado["exito"])

    def test_total_coincide_con_longitud_de_lista(self):
        resultado = _consultar(JD_EJEMPLO)
        self.assertEqual(resultado["total"], len(resultado["candidatos"]))

    def test_candidatos_tienen_campos_requeridos(self):
        resultado = _consultar(JD_EJEMPLO)
        campos_requeridos = ["id", "nombre", "texto_cv", "score_embedding"]
        for candidato in resultado["candidatos"]:
            for campo in campos_requeridos:
                self.assertIn(
                    campo, candidato,
                    f"Campo '{campo}' faltante en candidato {candidato.get('id', '?')}"
                )

    def test_score_embedding_es_float_entre_0_y_1(self):
        resultado = _consultar(JD_EJEMPLO)
        for candidato in resultado["candidatos"]:
            self.assertIsInstance(candidato["score_embedding"], float)
            self.assertGreaterEqual(candidato["score_embedding"], 0.0)
            self.assertLessEqual(candidato["score_embedding"], 1.0)

    def test_texto_cv_no_esta_vacio(self):
        resultado = _consultar(JD_EJEMPLO)
        for candidato in resultado["candidatos"]:
            self.assertGreater(len(candidato["texto_cv"]), 0)

    def test_chunks_se_agrupan_por_documento(self):
        # 3 chunks de 2 documentos → 2 candidatos.
        resultado = _consultar(JD_EJEMPLO)
        self.assertEqual(resultado["total"], 2)
        nombres = {c["nombre"] for c in resultado["candidatos"]}
        self.assertEqual(nombres, {"Julian Monte", "Ana Penacchioni"})

    def test_ordenados_por_score_descendente(self):
        resultado = _consultar(JD_EJEMPLO)
        scores = [c["score_embedding"] for c in resultado["candidatos"]]
        self.assertEqual(scores, sorted(scores, reverse=True))
        # El mejor chunk (0.81) define el score del candidato top.
        self.assertEqual(resultado["candidatos"][0]["nombre"], "Julian Monte")
        self.assertEqual(resultado["candidatos"][0]["score_embedding"], 0.81)

    def test_sin_resultados_devuelve_lista_vacia(self):
        resultado = _consultar(JD_EJEMPLO, chunks=[])
        self.assertFalse(resultado["exito"])
        self.assertEqual(resultado["total"], 0)
        self.assertEqual(resultado["candidatos"], [])

    def test_error_de_mcp_degrada_sin_romper(self):
        async_mock = mock.AsyncMock(side_effect=ConnectionError("MCP caído"))
        with mock.patch(
            "agentes.busquedas_internas.tools.consultar_ats.buscar_chunks", async_mock
        ):
            resultado = asyncio.run(Consultar_ats(JD_EJEMPLO))
        self.assertFalse(resultado["exito"])
        self.assertEqual(resultado["candidatos"], [])
        self.assertIn("MCP", resultado["mensaje"])


# ---------------------------------------------------------------------------
# Tests: agrupamiento de chunks (lógica pura, sin red)
# ---------------------------------------------------------------------------
class TestAgrupamientoChunks(unittest.TestCase):
    def test_reconstruye_texto_en_orden_de_chunk_index(self):
        chunks = [
            {"score": 0.5, "text": "segundo", "source_file": "X.pptx", "chunk_index": 1},
            {"score": 0.9, "text": "primero", "source_file": "X.pptx", "chunk_index": 0},
        ]
        candidatos = _agrupar_chunks_por_cv(chunks)
        self.assertEqual(len(candidatos), 1)
        self.assertEqual(candidatos[0].texto_cv, "primero\n\nsegundo")
        # Score del candidato = mejor score de sus chunks.
        self.assertEqual(candidatos[0].score_embedding, 0.9)
        self.assertEqual(candidatos[0].nombre, "X")


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
