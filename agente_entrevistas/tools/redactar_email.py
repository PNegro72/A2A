"""
Tool: redactar_email
Genera el cuerpo del email para el candidato usando Claude Haiku.
"""

import os
import anthropic


def _get_client():
    return anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])

_MODEL = "claude-haiku-4-5"


def redactar_email(
    candidato_nombre: str,
    proceso_titulo: str,
    skills_clave: list[str],
    empresa_nombre: str | None = None,
    idioma: str = "espanol",
    tono: str = "profesional y calido",
    info_adicional: str | None = None,
) -> dict:
    empresa_str = f"en {empresa_nombre}" if empresa_nombre else "en nuestra organizacion"
    skills_str  = ", ".join(skills_clave[:4]) if skills_clave else "tu perfil"
    info_str    = f"\nInformacion adicional a incluir: {info_adicional}" if info_adicional else ""

    prompt = f"""Redacta un email profesional para contactar a un candidato sobre una oportunidad laboral.

Datos:
- Nombre del candidato: {candidato_nombre}
- Posicion: {proceso_titulo}
- Skills relevantes a mencionar: {skills_str}
- Empresa: {empresa_str}
- Idioma: {idioma}
- Tono: {tono}{info_str}

Instrucciones:
- Saludo personalizado con el nombre del candidato
- Menciona brevemente por que su perfil es interesante
- Describe la oportunidad en 2-3 oraciones sin revelar datos confidenciales
- Cierra con un CTA claro: pidele que responda este email si le interesa saber mas
- Firma como "El equipo de Talent Acquisition"
- NO incluyas el asunto en el cuerpo
- Longitud: entre 120 y 200 palabras

Devuelve SOLO el cuerpo del email en texto plano, sin ningun comentario adicional."""

    try:
        response = _get_client().messages.create(
            model=_MODEL,
            max_tokens=1024,
            messages=[{"role": "user", "content": prompt}],
        )
        cuerpo_texto = response.content[0].text.strip()
    except Exception as e:
        return {"error": f"Error generando email con Claude: {e}"}

    parrafos    = [p.strip() for p in cuerpo_texto.split("\n\n") if p.strip()]
    cuerpo_html = "\n".join(f"<p>{p.replace(chr(10), '<br>')}</p>" for p in parrafos)

    return {
        "asunto":       f"Oportunidad laboral: {proceso_titulo}",
        "cuerpo_texto": cuerpo_texto,
        "cuerpo_html":  cuerpo_html,
        "idioma":       idioma,
    }