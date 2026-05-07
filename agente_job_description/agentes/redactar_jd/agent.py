"""
Agente Redactor de Job Descriptions — ADK LlmAgent.

Recibe una request corta del usuario (una oración o frase) y devuelve una JD
completa, bien estructurada, en formato JobDescriptionRedactada usando Claude
vía output_schema de ADK.

Detecta automáticamente el idioma (es/en) de la request y genera la JD
en ese mismo idioma. También parsea cantidad_candidatos si se menciona.
"""
import os

from dotenv import load_dotenv
from google.adk.agents import LlmAgent
from google.adk.models.lite_llm import LiteLlm

from agentes.config.settings import get_settings
from schemas import JobDescriptionRedactada

load_dotenv()


def _read_prompt(filename: str) -> str:
    """Lee el archivo de prompt desde el mismo directorio que este módulo."""
    script_dir = os.path.dirname(os.path.abspath(__file__))
    with open(os.path.join(script_dir, filename), "r", encoding="utf-8") as f:
        return f.read()


settings = get_settings()
os.environ["ANTHROPIC_API_KEY"] = settings.CLAUDE_API_KEY

root_agent = LlmAgent(
    name="redactar_jd",
    description=(
        "Genera una Job Description completa y estructurada a partir de una "
        "request corta del usuario. Detecta el idioma automáticamente y "
        "extrae la cantidad de candidatos si se menciona."
    ),
    model=LiteLlm(model=f"anthropic/{settings.CLAUDE_MODEL}"),
    instruction=_read_prompt("agent-prompt.txt"),
    output_schema=JobDescriptionRedactada,
)