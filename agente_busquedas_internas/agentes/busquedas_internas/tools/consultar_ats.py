"""
Herramienta: consultar_ats

Busca candidatos internos relevantes para una posición.

Actualmente delega en cvs.py, que usa búsqueda semántica sobre archivos .pptx
locales como reemplazo temporal de Workday.

Cuando la integración real con Workday esté disponible (ver workday_api_service.py),
solo este archivo cambia. El contrato de entrada/salida se mantiene idéntico,
y el resto del sistema (cvs.py, agent.py, tests) no necesita modificaciones.
"""
from agentes.busquedas_internas.cvs import Buscar_candidatos_similares
from schemas.busqueda_response import Busqueda_response
from schemas.cvs_data import Cvs_data
from schemas.JobDescriptionEstructurada import JobDescriptionEstructurada


def Consultar_ats(job_description: JobDescriptionEstructurada) -> dict:
    """
    Busca candidatos internos relevantes para una posición.

    Retorna los CVs más similares a la JD usando búsqueda semántica.
    Cada candidato incluye el texto completo de su CV para que el LLM pueda
    extraer los campos estructurados (nombre, skills, experiencia, etc.) y rankearlo.

    Args:
        job_description: Job Description estructurada con role_title, role_description,
                         management_level y skills.

    Returns:
        dict con estructura:
            {
                "exito": bool,
                "candidatos": list[dict],
                "total": int,
                "mensaje": str
            }

        Cada elemento de "candidatos":
            {
                "id": str,               # nombre del archivo sin extensión
                "nombre": str,           # nombre completo (del nombre de archivo)
                "texto_cv": str,         # texto completo del CV extraído del .pptx
                "score_embedding": float # similitud semántica con la JD (0.0–1.0)
            }
    """
    jd_texto = " ".join([
        job_description.role_title,
        job_description.role_description,
        job_description.management_level,
        " ".join(job_description.skills),
    ])
    candidatos: list[Cvs_data] = Buscar_candidatos_similares(jd_texto, top_n=10)

    response = Busqueda_response(
        exito=bool(candidatos),
        candidatos=candidatos,
        total=len(candidatos),
        mensaje=(
            f"Se encontraron {len(candidatos)} CVs relevantes."
            if candidatos
            else "No se encontraron CVs en el directorio configurado."
        ),
    )
    return response.model_dump(exclude={"candidatos": {"__all__": {"embedding"}}})