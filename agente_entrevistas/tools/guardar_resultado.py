"""
Tool: guardar_resultado
Persiste el resultado en Supabase y retorna la señal de éxito al orquestador.
Este tool SIEMPRE debe ser el último en ejecutarse.
"""

import os
from datetime import datetime, timezone
from supabase import create_client, Client


def _get_supabase() -> Client:
    return create_client(
        os.environ["SUPABASE_URL"],
        os.environ["SUPABASE_SERVICE_KEY"],
    )


def guardar_resultado(
    candidato_id: str,
    proceso_id: str,
    candidato_nombre: str,
    preguntas_total: int,
    kit_path_docx: str,
    kit_path_pdf: str | None = None,
    duracion_estimada_min: int | None = None,
    notas: str | None = None,
) -> dict:
    """
    Guarda el resultado del kit de entrevista en la tabla `entrevistas` de Supabase
    y retorna la señal de éxito que el orquestador espera.

    Args:
        candidato_id: UUID del candidato.
        proceso_id: UUID del proceso de selección.
        candidato_nombre: Nombre del candidato (para el registro).
        preguntas_total: Cantidad total de preguntas generadas.
        kit_path_docx: Ruta al archivo .docx del kit generado.
        kit_path_pdf: Ruta al archivo .pdf (opcional).
        duracion_estimada_min: Duración estimada de la entrevista en minutos.
        notas: Cualquier observación adicional del agente.

    Returns:
        Dict con status "éxito" y metadata para el orquestador.
    """
    sb = _get_supabase()

    registro = {
        "candidato_id":          candidato_id,
        "proceso_id":            proceso_id,
        "candidato_nombre":      candidato_nombre,
        "preguntas_total":       preguntas_total,
        "kit_path_docx":         kit_path_docx,
        "kit_path_pdf":          kit_path_pdf,
        "duracion_estimada_min": duracion_estimada_min,
        "notas":                 notas,
        "estado":                "kit_generado",
        "generado_en":           datetime.now(timezone.utc).isoformat(),
    }

    try:
        res = sb.table("entrevistas").insert(registro).execute()
        entrevista_id = res.data[0]["id"] if res.data else None

        return {
            "estado":               "éxito",
            "entrevista_id":        entrevista_id,
            "candidato_id":         candidato_id,
            "proceso_id":           proceso_id,
            "preguntas_total":      preguntas_total,
            "kit_path_docx":        kit_path_docx,
            "kit_path_pdf":         kit_path_pdf,
            "guardado_en_supabase": True,
        }

    except Exception as e:
        return {
            "estado":               "éxito_con_advertencia",
            "advertencia":          f"Kit generado pero falló el guardado en Supabase: {e}",
            "candidato_id":         candidato_id,
            "proceso_id":           proceso_id,
            "preguntas_total":      preguntas_total,
            "kit_path_docx":        kit_path_docx,
            "guardado_en_supabase": False,
        }
