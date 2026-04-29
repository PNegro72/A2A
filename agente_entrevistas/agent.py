"""
Agente Entrevistas — Google ADK + OpenAI (vía LiteLLM)
Invocado como AgentTool desde el Orquestador principal.

Responsabilidades:
- Leer perfil del candidato y JD desde Supabase
- Generar preguntas técnicas y conductuales adaptadas
- Buscar información pública del candidato/empresa (web_search)
- Generar el kit de entrevista (Word/PDF)
- Redactar y crear borrador de email en Outlook para el candidato
- Retornar señal de éxito al orquestador con metadata
"""

from google.adk.agents import Agent
from google.adk.models.lite_llm import LiteLlm

from agente_entrevistas.tools.leer_candidato_mock import leer_candidato
from agente_entrevistas.tools.generar_preguntas import generar_preguntas
from agente_entrevistas.tools.web_search import web_search
from agente_entrevistas.tools.generar_kit import generar_kit
from agente_entrevistas.tools.guardar_resultado import guardar_resultado
from agente_entrevistas.tools.redactar_email import redactar_email
from agente_entrevistas.tools.crear_borrador_email import crear_borrador_email
from agente_entrevistas.prompts.system_prompt import SYSTEM_PROMPT
from agente_entrevistas.utils.config import OPENAI_MODEL

# LiteLLM enruta a OpenAI. Requiere OPENAI_API_KEY en el .env.
# El modelo se configura con OPENAI_MODEL (default: gpt-4o-mini),
# alineado con los demás agentes del repo.
MODEL = LiteLlm(model=f"openai/{OPENAI_MODEL}")

agente_entrevistas = Agent(
    name="agente_entrevistas",
    model=MODEL,
    description=(
        "Prepara una entrevista técnica completa dado un candidato y un JD. "
        "Genera preguntas adaptadas, verifica información pública del candidato, "
        "produce el kit de entrevista en Word/PDF y crea un borrador de email "
        "en Outlook para contactar al candidato si está interesado en la búsqueda."
    ),
    instruction=SYSTEM_PROMPT,
    tools=[
        leer_candidato,
        generar_preguntas,
        web_search,
        generar_kit,
        guardar_resultado,
        redactar_email,
        crear_borrador_email,
    ],
)
root_agent = agente_entrevistas