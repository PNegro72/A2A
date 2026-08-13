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

import os

from google.adk.agents import Agent
from google.adk.models.lite_llm import LiteLlm

from tools.generar_preguntas import generar_preguntas
from tools.web_search import web_search
from tools.generar_kit import generar_kit
from tools.redactar_email import redactar_email
from tools.crear_borrador_email import crear_borrador_email
from prompts.system_prompt import SYSTEM_PROMPT
from utils.config import OPENAI_API_KEY, OPENAI_MODEL

MODEL = LiteLlm(
    model=f"openai/{OPENAI_MODEL}",
    reasoning_effort="none",
)

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
    # NOTA: `leer_candidato` y `guardar_resultado` (lectura/persistencia en
    # Supabase) figuraban en esta lista pero nunca se implementaron ni existían
    # como import, por lo que este módulo tiraba NameError al importarse.
    # Se quitan hasta que exista una implementación real; el perfil del
    # candidato hoy llega en el payload HTTP (ver server.py).
    tools=[
        generar_preguntas,
        web_search,
        generar_kit,
        redactar_email,
        crear_borrador_email,
    ],
)
root_agent = agente_entrevistas