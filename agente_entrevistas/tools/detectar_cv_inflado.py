"""
Tool: detectar_cv_inflado
Analiza el CV de un candidato con OpenAI y detecta posibles exageraciones
o inconsistencias entre lo declarado y el nivel real esperado.
"""

import os
import json
import re
import openai
from datetime import datetime


def _get_client():
    return openai.OpenAI(api_key=os.environ["OPENAI_API_KEY"])


def _get_model() -> str:
    return os.environ["OPENAI_MODEL"]
 
 
def _limpiar_json(raw: str) -> str:
    """Limpia el JSON devuelto por el LLM antes de parsearlo."""
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
 
 
def detectar_cv_inflado(
    cv_texto: str,
    skills_declarados: list[str],
    experiencia: list[dict],
    nivel_esperado: str = "senior",
    experiencia_total_calculada: str | None = None,
) -> dict:
    if not cv_texto and not skills_declarados and not experiencia:
        return {
            "inflation_score": 0,
            "red_flags": [],
            "preguntas_presion": [],
            "resumen": "No hay suficiente informacion para analizar.",
        }
 
    experiencia_str = "\n".join([
        f"- {e.get('cargo', '')} en {e.get('empresa', '')} "
        f"({e.get('desde', '?')} -> {e.get('hasta') or 'actual'}): "
        f"{e.get('descripcion', '')}"
        for e in experiencia
    ])
 
    fecha_hoy = datetime.now().strftime("%B %Y")
 
    prompt = f"""Sos un experto en reclutamiento tecnico con 15 anos de experiencia evaluando CVs.
La fecha actual es {fecha_hoy}. Usa esto como referencia para evaluar si las fechas del CV son pasadas, presentes o futuras.
 
=== CV ===
{cv_texto[:3000] if cv_texto else "No disponible"}
 
=== SKILLS DECLARADOS ===
{", ".join(skills_declarados) if skills_declarados else "No especificados"}
 
=== EXPERIENCIA LABORAL ===
{experiencia_str if experiencia_str else "No disponible"}
 
=== NIVEL DEL PUESTO ===
{nivel_esperado}
 
=== EXPERIENCIA TOTAL (calculada en Python, es correcta) ===
{experiencia_total_calculada or "No disponible"}
Usa este dato como la experiencia real del candidato. No recalcules vos mismo.
 
Analiza el CV y detecta exageraciones, inconsistencias o claims sospechosos.
Senales a buscar: experiencia declarada vs real, saltos de cargo rapidos, logros vagos, fechas inconsistentes, empresas inexistentes.
 
Devuelve UNICAMENTE este JSON valido sin texto adicional. No uses comillas tipograficas ni comas finales:
{{
  "inflation_score": 0,
  "red_flags": [
    {{
      "claim": "descripcion del claim",
      "razon": "por que es sospechoso",
      "severidad": "alta"
    }}
  ],
  "preguntas_presion": [
    {{
      "pregunta": "pregunta para verificar",
      "objetivo": "que se evalua",
      "red_flag_relacionado": "claim relacionado"
    }}
  ],
  "resumen": "evaluacion general en 2-3 oraciones"
}}"""
 
    raw = ""
    try:
        response = _get_client().chat.completions.create(
            model=_get_model(),
            # NOTA (2026-08-05): gpt-5.6-* rechaza max_tokens ("Unsupported
            # parameter") — la Chat Completions API lo reemplazó por este.
            max_completion_tokens=2048,
            messages=[{"role": "user", "content": prompt}],
        )
        raw = response.choices[0].message.content.strip()
        raw = _limpiar_json(raw)
        data = json.loads(raw)
 
        return {
            "inflation_score":   int(data.get("inflation_score", 0)),
            "red_flags":         data.get("red_flags", []),
            "preguntas_presion": data.get("preguntas_presion", []),
            "resumen":           data.get("resumen", ""),
        }
 
    except json.JSONDecodeError as e:
        return {"error": f"Error parseando respuesta: {e}", "raw": raw[:500] if raw else ""}
    except Exception as e:
        return {"error": f"Error analizando CV: {e}"}