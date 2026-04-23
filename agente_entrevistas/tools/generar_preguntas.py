"""
Tool: generar_preguntas
Genera preguntas de entrevista personalizadas usando Claude Haiku con structured output.
"""

import os
import json
import anthropic
from agente_entrevistas.models.schemas import Pregunta, PreguntasOutput


def _get_client():
    return anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])

_MODEL  = "claude-haiku-4-5"


def generar_preguntas(
    candidato_nombre: str,
    skills: list[str],
    experiencia: list[dict],
    cv_texto: str | None,
    jd_texto: str | None,
    info_publica: str | None,
    nivel_estimado: str = "semi",
    n_preguntas_tecnicas: int = 8,
    n_preguntas_conductuales: int = 4,
    n_preguntas_presion: int = 3,
) -> dict:
    """
    Genera un set de preguntas de entrevista personalizadas para el candidato.

    Args:
        candidato_nombre: Nombre completo del candidato.
        skills: Lista de skills declarados en el CV.
        experiencia: Lista de experiencias laborales (empresa, cargo, descripcion).
        cv_texto: Texto completo del CV (opcional).
        jd_texto: Texto del Job Description (opcional pero recomendado).
        info_publica: Resultados de web_search sobre el candidato (opcional).
        nivel_estimado: Nivel inferido del candidato ("junior" | "semi" | "senior").
        n_preguntas_tecnicas: Cantidad de preguntas tecnicas a generar.
        n_preguntas_conductuales: Cantidad de preguntas conductuales (STAR).
        n_preguntas_presion: Preguntas para detectar exageracion en el CV.

    Returns:
        Diccionario con lista de preguntas categorizadas y duracion estimada.
    """
    experiencia_str = "\n".join([
        f"- {e.get('cargo', '')} en {e.get('empresa', '')} "
        f"({e.get('desde', '?')}) -> {e.get('hasta') or 'actual'}): "
        f"{e.get('descripcion', '')}"
        for e in experiencia
    ])

    prompt = f"""Sos un experto en entrevistas tecnicas de RRHH y tecnologia.

Genera preguntas de entrevista PERSONALIZADAS para el siguiente candidato.
Las preguntas deben hacer referencia a sus empresas, proyectos y skills REALES.
NO generes preguntas genericas que podrian hacerse a cualquier candidato.

=== CANDIDATO ===
Nombre: {candidato_nombre}
Nivel estimado: {nivel_estimado}
Skills declarados: {", ".join(skills) if skills else "No especificados"}

Experiencia laboral:
{experiencia_str if experiencia_str else "No disponible"}

CV completo (extracto):
{cv_texto[:2000] if cv_texto else "No disponible"}

=== JOB DESCRIPTION ===
{jd_texto[:1500] if jd_texto else "No disponible"}

=== INFORMACION PUBLICA ===
{info_publica[:1000] if info_publica else "No encontrada"}

=== INSTRUCCIONES ===
Genera exactamente:
- {n_preguntas_tecnicas} preguntas tecnicas (categoria: "tecnica")
- {n_preguntas_conductuales} preguntas conductuales STAR (categoria: "conductual")
- {n_preguntas_presion} preguntas de presion para detectar CV exagerado (categoria: "presion")

Para cada pregunta incluye:
- "categoria": "tecnica" | "conductual" | "presion"
- "pregunta": el texto de la pregunta (especifica, no generica)
- "objetivo": que evaluas con esta pregunta (1 oracion)
- "nivel": "{nivel_estimado}"
- "tiempo_estimado_min": minutos estimados para responder

Responde UNICAMENTE con un JSON valido, sin texto adicional, con esta estructura:
{{
  "total": <numero total>,
  "preguntas": [ ... ],
  "duracion_estimada_min": <suma de tiempos>
}}"""

    try:
        response = _get_client().messages.create(
            model=_MODEL,
            max_tokens=4096,
            messages=[{"role": "user", "content": prompt}],
        )
        raw = response.content[0].text.strip()

        # Limpiar posibles markdown fences
        if raw.startswith("```"):
            raw = raw.split("```")[1]
            if raw.startswith("json"):
                raw = raw[4:]
        raw = raw.strip()

        data   = json.loads(raw)
        output = PreguntasOutput(**data)
        return output.model_dump()

    except json.JSONDecodeError as e:
        return {"error": f"Error parseando JSON: {e}", "raw": raw if "raw" in dir() else ""}
    except Exception as e:
        return {"error": f"Error llamando a Claude: {e}"}
