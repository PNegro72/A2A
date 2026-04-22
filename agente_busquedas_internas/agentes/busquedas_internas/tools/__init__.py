from agentes.busquedas_internas.tools.consultar_ats import consultar_ats

# rankear_candidatos fue eliminado: el LlmAgent realiza el ranking directamente
# como parte de su output, sin necesidad de delegar a una tool que llame a Gemini.
# insertar_supabase fue eliminado: la persistencia es responsabilidad del orquestador.
__all__ = ["consultar_ats"]
