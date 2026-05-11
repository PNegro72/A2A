"""
Agente Búsquedas Internas — ADK LlmAgent.

Recibe una JobDescriptionEstructurada (JSON), consulta el ATS, rankea
los candidatos con su propio razonamiento LLM y retorna un ResultadoRanking.
La persistencia del resultado (Supabase) es responsabilidad del orquestador.
"""
import os

from dotenv import load_dotenv
from google.adk.agents import LlmAgent
from google.adk.models.lite_llm import LiteLlm

from agentes.busquedas_internas.tools.consultar_ats import Consultar_ats
from agentes.config.settings import get_settings
from schemas.ResultadoRanking import ResultadoRanking

# pydantic-settings carga el .env en sus atributos pero NO actualiza os.environ.
# ADK/LiteLLM necesita ANTHROPIC_API_KEY en os.environ para autenticar con Claude;
# como el .env usa CLAUDE_API_KEY, lo aliasamos abajo después de get_settings().
load_dotenv()


def _read_prompt(filename: str) -> str:
    """Lee el archivo de prompt desde el mismo directorio que este módulo."""
    script_dir = os.path.dirname(os.path.abspath(__file__))
    with open(os.path.join(script_dir, filename), "r", encoding="utf-8") as f:
        return f.read()


settings = get_settings()
os.environ["ANTHROPIC_API_KEY"] = settings.CLAUDE_API_KEY

# armo el root_agent con el ADK de Google.
root_agent = LlmAgent(
    name="busquedas_internas",
    description=(
        "Recibe una Job Description estructurada, busca candidatos internos en el ATS "
        "y los rankea con IA. Retorna un ResultadoRanking al orquestador."
    ),
    model=LiteLlm(model=f"anthropic/{settings.CLAUDE_MODEL}"),
    instruction=_read_prompt("agent-prompt.txt"),
    tools=[Consultar_ats],
    output_schema=ResultadoRanking,
)
