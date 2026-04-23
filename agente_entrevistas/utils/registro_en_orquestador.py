"""
Snippet de cómo registrar agente_entrevistas como AgentTool en el orquestador.
Este archivo es solo referencia — va en el proyecto del orquestador.
"""

from google.adk.agents import Agent
from google.adk.tools.agent_tool import AgentTool
from agente_entrevistas.agent import agente_entrevistas

orquestador = Agent(
    name="orquestador_reclutamiento",
    model=...,
    instruction=...,
    tools=[
        # ... otros tools del orquestador ...
        AgentTool(agent=agente_entrevistas),
    ],
)

# El orquestador invoca al agente con:
# {
#   "candidato_id": "uuid-del-candidato",
#   "proceso_id":   "uuid-del-proceso",
#   "jd_texto":     "Buscamos un senior backend engineer..."   <- opcional
# }
#
# Si además quiere que se genere el borrador de email:
# {
#   "candidato_id":   "uuid-del-candidato",
#   "proceso_id":     "uuid-del-proceso",
#   "enviar_email":   true,
#   "empresa_nombre": "Acme Corp"   <- opcional, puede omitirse si es confidencial
# }
