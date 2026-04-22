# Convención ADK: exportar el módulo `agent` (no el objeto directamente)
# para que `adk web agentes/busquedas_internas` pueda acceder a `agent.root_agent`.
from . import agent

__all__ = ["agent"]
