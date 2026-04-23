"""
Tool: leer_candidato
Lee el perfil completo del candidato y el JD del proceso desde Supabase.
"""

import os
from supabase import create_client, Client
from agente_entrevistas.models.schemas import Candidato, ExperienciaLaboral


def _get_supabase() -> Client:
    return create_client(
        os.environ["SUPABASE_URL"],
        os.environ["SUPABASE_SERVICE_KEY"],
    )


def leer_candidato(candidato_id: str, proceso_id: str) -> dict:
    """
    Lee el perfil del candidato y el Job Description asociado al proceso desde Supabase.

    Args:
        candidato_id: UUID del candidato.
        proceso_id: UUID del proceso de selección (para obtener el JD).

    Returns:
        Diccionario con el perfil completo del candidato y el texto del JD.
    """
    sb = _get_supabase()

    res_candidato = (
        sb.table("candidatos")
        .select("*")
        .eq("id", candidato_id)
        .single()
        .execute()
    )
    if not res_candidato.data:
        return {"error": f"Candidato {candidato_id} no encontrado en Supabase."}

    raw = res_candidato.data

    experiencia = []
    for exp in raw.get("experiencia", []):
        experiencia.append(ExperienciaLaboral(**exp).model_dump())

    candidato = Candidato(
        candidato_id=candidato_id,
        nombre=raw.get("nombre", ""),
        email=raw.get("email"),
        linkedin_url=raw.get("linkedin_url"),
        github_username=raw.get("github_username"),
        skills=raw.get("skills", []),
        experiencia=experiencia,
        cv_texto=raw.get("cv_texto"),
    )

    res_proceso = (
        sb.table("procesos")
        .select("titulo, jd_texto")
        .eq("id", proceso_id)
        .single()
        .execute()
    )

    jd_texto = None
    proceso_titulo = ""
    if res_proceso.data:
        jd_texto = res_proceso.data.get("jd_texto")
        proceso_titulo = res_proceso.data.get("titulo", "")

    result = candidato.model_dump()
    result["jd_texto"] = jd_texto
    result["proceso_titulo"] = proceso_titulo

    return result
