"""
Agente Job Description — ADK LlmAgent.

Recibe un Job Description en texto libre y devuelve un JSON estructurado
(JobDescriptionEstructurada) usando OpenAI vía output_schema de ADK.

ADK gestiona la llamada al modelo, el parseo del JSON y la validación Pydantic.
El modelo OpenAI se accede a través del backend LiteLLM integrado en ADK.
"""
import os

from dotenv import load_dotenv
from google.adk.agents import LlmAgent
from google.adk.models.lite_llm import LiteLlm

from agentes.config.settings import get_settings
from schemas import JobDescriptionEstructurada

load_dotenv()


def _read_prompt(filename: str) -> str:
    """Lee el archivo de prompt desde el mismo directorio que este módulo."""
    script_dir = os.path.dirname(os.path.abspath(__file__))
    with open(os.path.join(script_dir, filename), "r", encoding="utf-8") as f:
        return f.read()


settings = get_settings()

root_agent = LlmAgent(
    name="job_description",
    description=(
        "Parsea Job Descriptions en texto libre y las estructura en JSON. "
        "Extrae título del rol, descripción, nivel de management y skills requeridas."
    ),
    model=LiteLlm(model=f"openai/{settings.OPENAI_MODEL}"),
    instruction=_read_prompt("agent-prompt.txt"),
    output_schema=JobDescriptionEstructurada,
)
