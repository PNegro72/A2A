"""
Tool: rankear_candidatos
Recibe una lista de CVs en texto plano y un Job Description,
y devuelve el Top N candidatos rankeados por fit.

Scoring:
- 40% skills match
- 30% experiencia relevante
- 20% nivel/seniority
- 10% otros factores (idiomas, educacion, etc.)
"""

import os
import json
import re
from openai import OpenAI
from datetime import datetime


def _get_client():
    return OpenAI(api_key=os.environ["OPENAI_API_KEY"])


def _get_model() -> str:
    return os.environ["OPENAI_MODEL"]


def _limpiar_json(raw: str) -> str:
    if "```" in raw:
        parts = raw.split("```")
        for part in parts:
            part = part.strip()
            if part.startswith("json"):
                part = part[4:]
            if part.strip().startswith("{"):
                raw = part.strip()
                break
    raw = raw.strip()
    raw = raw.replace('\u201c', '"').replace('\u201d', '"')
    raw = raw.replace('\u2018', "'").replace('\u2019', "'")
    raw = re.sub(r',\s*([}\]])', r'\1', raw)
    return raw


def rankear_candidatos(
    candidatos: list[dict],
    jd_texto: str,
    top_n: int = 3,
) -> dict:
    """
    Rankea una lista de candidatos contra un Job Description.

    Args:
        candidatos: Lista de dicts con:
            - nombre: str
            - cv_texto: str
            - filename: str (opcional)
        jd_texto: Texto del Job Description.
        top_n: Cantidad de candidatos a devolver en el ranking (default 3).

    Returns:
        Dict con lista de top_candidatos rankeados con score y justificacion.
    """
    if not candidatos:
        return {"error": "No se recibieron candidatos para rankear."}

    if not jd_texto:
        return {"error": "Se requiere un Job Description para rankear."}

    fecha_hoy = datetime.now().strftime("%B %Y")

    cvs_str = ""
    for i, c in enumerate(candidatos, 1):
        nombre   = c.get("nombre") or c.get("filename", f"Candidato {i}")
        cv_texto = (c.get("cv_texto") or "")[:2000]
        cvs_str += f"\n--- CANDIDATO {i}: {nombre} ---\n{cv_texto}\n"

    prompt = f"""Sos un experto en reclutamiento tecnico. La fecha actual es {fecha_hoy}.

Rankea los siguientes {len(candidatos)} candidatos contra el Job Description.

=== JOB DESCRIPTION ===
{jd_texto[:2000]}

=== CANDIDATOS ===
{cvs_str}

=== CRITERIOS (pesos) ===
- Skills match 40%: coincidencia de skills requeridos vs declarados
- Experiencia relevante 30%: anos y calidad en roles similares
- Nivel/seniority 20%: consistencia entre nivel declarado y experiencia real
- Otros 10%: idiomas, educacion, certificaciones relevantes

Evalua cada candidato y devuelve SOLO los top {top_n} por score.

Devuelve UNICAMENTE este JSON valido sin texto adicional:
{{
  "total_evaluados": {len(candidatos)},
  "top_candidatos": [
    {{
      "posicion": 1,
      "nombre": "nombre exacto del candidato",
      "score": 85,
      "skills_match": ["skill1", "skill2"],
      "skills_faltantes": ["skill3"],
      "anos_experiencia_relevante": 3,
      "justificacion": "por que es el mejor fit para este rol especifico",
      "recomendacion": "Avanzar"
    }}
  ],
  "resumen": "comparacion general en 2-3 oraciones"
}}

Para recomendacion usa exactamente uno de: "Avanzar", "Considerar", "Descartar".
No uses comillas tipograficas ni comas finales en el JSON.
"""

    raw = ""
    try:
        response = _get_client().chat.completions.create(
            model=_get_model(),
            max_completion_tokens=3000,
            messages=[{"role": "user", "content": prompt}],
            response_format={"type": "json_object"},
        )
        raw  = (response.choices[0].message.content or "").strip()
        raw  = _limpiar_json(raw)
        data = json.loads(raw)

        return {
            "total_evaluados": data.get("total_evaluados", len(candidatos)),
            "top_candidatos":  data.get("top_candidatos", [])[:top_n],
            "resumen":         data.get("resumen", ""),
        }

    except json.JSONDecodeError as e:
        return {"error": f"Error parseando respuesta: {e}", "raw": raw[:500]}
    except Exception as e:
        return {"error": f"Error rankeando candidatos: {e}"}