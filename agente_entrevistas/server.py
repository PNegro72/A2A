"""
Servidor HTTP para el agente entrevistas.

Expone POST /a2a/entrevistas aceptando el payload JSON plano que envía
el orchestrator (ej: {"action": "preparar_entrevista", "candidato_id": "...",
"proceso_id": "...", "enviar_email": false}) y retorna el output del agente ADK.

Lee toda la configuración del .env (HOST, PORT, LOG_LEVEL, CLAUDE_*, SUPABASE_*,
MS_*, KIT_OUTPUT_DIR, TAVILY_API_KEY/SERPER_API_KEY). Si alguna variable falta,
el agente falla al arrancar (fail-fast en utils/config.py).

Correr con (desde la carpeta agente_entrevistas/):
    python server.py
"""

import base64
import logging
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from dotenv import load_dotenv

load_dotenv(override=True)

from observability import init_observability  # noqa: E402 — must precede anthropic imports
init_observability("entrevistas")

from flask import Flask, jsonify, request, send_file  # noqa: E402
from flask_cors import CORS  # noqa: E402
from opentelemetry import trace  # noqa: E402

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)

_tracer = trace.get_tracer(__name__)

app = Flask(__name__)
CORS(app)


@app.route("/a2a/entrevistas", methods=["POST"])
def entrevistas():
    body   = request.get_json(silent=True) or {}
    action = body.get("action")

    if action == "preparar_entrevista":
        return _preparar_entrevista(body)

    if action == "enviar_email":
        return _enviar_email(body)

    return jsonify({
        "status":  "error",
        "message": f"Accion desconocida: '{action}'. Acciones disponibles: preparar_entrevista, enviar_email",
    }), 400


@app.route("/health", methods=["GET"])
def health():
    return jsonify({"status": "ok", "agent": "entrevistas_agent"})


@app.route("/download/<filename>", methods=["GET"])
def download_kit(filename: str):
    output_dir = Path(os.environ.get("KIT_OUTPUT_DIR", "./output/kits"))
    file_path  = output_dir / filename

    if not file_path.exists() or not file_path.suffix == ".docx":
        return jsonify({"status": "error", "message": "Archivo no encontrado."}), 404

    return send_file(
        str(file_path),
        as_attachment=True,
        download_name=filename,
        mimetype="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    )


def _extraer_texto_cv(cv_base64: str, mime_type: str) -> str | None:
    """
    Extrae el texto de un CV en PDF o Word a partir de su contenido base64.
    Retorna el texto extraído o None si falla.
    """
    try:
        file_bytes = base64.b64decode(cv_base64)

        if "pdf" in mime_type:
            import fitz  # PyMuPDF
            doc  = fitz.open(stream=file_bytes, filetype="pdf")
            text = "\n".join(page.get_text() for page in doc)
            doc.close()
            return text.strip() or None

        elif "word" in mime_type or "openxmlformats" in mime_type:
            import io
            from docx import Document
            doc  = Document(io.BytesIO(file_bytes))
            text = "\n".join(p.text for p in doc.paragraphs if p.text.strip())
            return text.strip() or None

        else:
            logger.warning("Tipo de archivo no soportado para extracción: %s", mime_type)
            return None

    except Exception as e:
        logger.error("Error extrayendo texto del CV: %s", e)
        return None


def _calcular_experiencia_total(experiencia: list[dict]) -> str:
    """Calcula el total de experiencia laboral en Python — sin LLM."""
    from datetime import datetime
    hoy         = datetime.now()
    total_meses = 0
    palabras_actual = {"actualidad", "actual", "presente", "present", "current", "hoy"}

    for exp in experiencia:
        try:
            desde     = datetime.strptime(exp.get("desde", ""), "%Y-%m")
            hasta_str = (exp.get("hasta") or "").strip().lower()
            if not hasta_str or hasta_str in palabras_actual:
                hasta = hoy
            else:
                hasta = datetime.strptime(hasta_str, "%Y-%m")
            meses = (hasta.year - desde.year) * 12 + (hasta.month - desde.month)
            if meses > 0:
                total_meses += meses
        except Exception:
            continue

    anios = total_meses // 12
    meses = total_meses % 12
    return f"{anios} años y {meses} meses"


def _enviar_email(body: dict):
    """Acción independiente: solo redacta y manda el email, sin regenerar el kit."""
    candidato_nombre = body.get("candidato_nombre", "")
    candidato_email  = body.get("candidato_email", "")
    proceso_titulo   = body.get("proceso_titulo", "")
    skills_clave     = body.get("skills_clave", [])

    if not candidato_email:
        return jsonify({"status": "error", "message": "candidato_email es requerido."}), 400

    logger.info("Enviando email | candidato=%s email=%s", candidato_nombre, candidato_email)

    with _tracer.start_as_current_span("entrevistas.enviar-email") as span:
        span.set_attribute("input.candidato", candidato_nombre)
        span.set_attribute("input.proceso", proceso_titulo)
        try:
            from tools.redactar_email import redactar_email
            email_result = redactar_email(
                candidato_nombre=candidato_nombre,
                proceso_titulo=proceso_titulo,
                skills_clave=skills_clave[:4],
            )

            if "error" in email_result:
                span.set_attribute("error", email_result["error"])
                return jsonify({"status": "error", "message": email_result["error"]}), 500

            from tools.crear_borrador_email import crear_borrador_email
            send_result = crear_borrador_email(
                candidato_nombre=candidato_nombre,
                candidato_email=candidato_email,
                proceso_titulo=proceso_titulo,
                cuerpo_email=email_result.get("cuerpo_texto", ""),
                asunto=email_result.get("asunto"),
            )

            if send_result.get("status") == "enviado":
                span.set_attribute("output.email_enviado", True)
                return jsonify({
                    "status":        "ok",
                    "email_enviado": True,
                    "asunto":        send_result.get("asunto"),
                    "destinatario":  candidato_email,
                })
            else:
                span.set_attribute("error", send_result.get("error", "Error enviando email"))
                return jsonify({
                    "status":  "error",
                    "message": send_result.get("error", "Error enviando email"),
                }), 500

        except Exception as exc:
            logger.exception("Error en _enviar_email")
            span.set_attribute("error", str(exc))
            return jsonify({"status": "error", "message": str(exc)}), 500


def _preparar_entrevista(body: dict):
    candidato_id = body.get("candidato_id")
    proceso_id   = body.get("proceso_id")

    if not candidato_id or not proceso_id:
        return jsonify({
            "status":  "error",
            "message": "candidato_id y proceso_id son requeridos.",
        }), 400

    jd_texto  = body.get("jd_texto")
    candidato = body.get("candidato", {})

    if not candidato:
        return jsonify({
            "status":  "error",
            "message": "Se requiere el campo 'candidato' con el perfil del candidato.",
        }), 400

    candidato_nombre = candidato.get("nombre", "")
    skills           = candidato.get("skills", [])
    experiencia      = candidato.get("experiencia", [])
    proceso_titulo   = candidato.get("proceso_titulo", "")

    # cv_texto puede venir directo o extraerse del archivo base64
    cv_texto      = candidato.get("cv_texto")
    cv_base64     = body.get("cv_base64")
    cv_mime_type  = body.get("cv_mime_type", "application/pdf")
    cv_filename   = body.get("cv_filename", "cv.pdf")

    if cv_base64 and not cv_texto:
        logger.info("Extrayendo texto del CV: %s (%s)", cv_filename, cv_mime_type)
        cv_texto = _extraer_texto_cv(cv_base64, cv_mime_type)
        if cv_texto:
            logger.info("CV extraído: %d caracteres", len(cv_texto))
        else:
            logger.warning("No se pudo extraer texto del CV")

    logger.info("Preparando entrevista | candidato=%s proceso=%s cv=%s",
                candidato_id, proceso_id, "sí" if cv_texto else "no")

    with _tracer.start_as_current_span("entrevistas.preparar-entrevista") as span:
        span.set_attribute("input.candidato_id", candidato_id)
        span.set_attribute("input.proceso_id", proceso_id)
        span.set_attribute("input.candidato_nombre", candidato_nombre)
        span.set_attribute("input.has_cv", cv_texto is not None)
        try:
            # 1. Web search — prefer profile_url (Himalayas/GitHub direct link),
            #    then linkedin_url, then github_username, then name fallback
            from tools.web_search import web_search

            profile_url = candidato.get("profile_url")
            if profile_url:
                query = f"{candidato_nombre} {profile_url}"
            elif candidato.get("linkedin_url"):
                query = f"{candidato_nombre} {candidato['linkedin_url']}"
            elif candidato.get("github_username"):
                query = f"{candidato_nombre} github {candidato['github_username']}"
            else:
                query = f"{candidato_nombre} software engineer"

            logger.info("Web search query: %s", query)
            search_result = web_search(query, max_results=5)
            info_publica = ""
            if search_result.get("resultados"):
                info_publica = "\n".join([
                    f"- {r['titulo']}: {r['snippet']}"
                    for r in search_result["resultados"]
                ])

            for exp in experiencia[:2]:
                empresa = exp.get("empresa", "")
                if empresa:
                    r = web_search(f"{empresa} empresa Argentina tecnologia", max_results=2)
                    if r.get("resultados"):
                        info_publica += f"\n- {empresa}: {r['resultados'][0].get('snippet', '')}"

            # 2. Detectar CV inflado (si hay cv_texto)
            cv_inflado_result    = {}
            preguntas_presion_cv = []

            if cv_texto:
                from tools.detectar_cv_inflado import detectar_cv_inflado
                logger.info("EXPERIENCIA DEBUG | %s", experiencia)
                experiencia_total = _calcular_experiencia_total(experiencia)
                cv_inflado_result = detectar_cv_inflado(
                    cv_texto=cv_texto,
                    skills_declarados=skills,
                    experiencia=experiencia,
                    nivel_esperado="senior",
                    experiencia_total_calculada=experiencia_total,
                )
                if "error" not in cv_inflado_result:
                    preguntas_presion_cv = cv_inflado_result.get("preguntas_presion", [])
                    logger.info(
                        "CV analizado | inflation_score=%s red_flags=%d",
                        cv_inflado_result.get("inflation_score"),
                        len(cv_inflado_result.get("red_flags", [])),
                    )
                else:
                    logger.warning("Error analizando CV: %s", cv_inflado_result.get("error"))

            # 3. Generar preguntas
            from tools.generar_preguntas import generar_preguntas

            preguntas_result = generar_preguntas(
                candidato_nombre=candidato_nombre,
                skills=skills,
                experiencia=experiencia,
                cv_texto=cv_texto,
                jd_texto=jd_texto,
                info_publica=info_publica or None,
            )

            if "error" in preguntas_result:
                span.set_attribute("error", preguntas_result["error"])
                return jsonify({"status": "error", "message": preguntas_result["error"]}), 500

            preguntas         = preguntas_result.get("preguntas", [])
            duracion_estimada = preguntas_result.get("duracion_estimada_min")

            # Agregar preguntas de presión del análisis de CV inflado
            for pp in preguntas_presion_cv:
                preguntas.append({
                    "categoria":           "presion",
                    "pregunta":            pp.get("pregunta", ""),
                    "objetivo":            pp.get("objetivo", ""),
                    "nivel":               "senior",
                    "tiempo_estimado_min": 5,
                })

            # 4. Generar kit
            from tools.generar_kit import generar_kit

            kit_result = generar_kit(
                candidato_id=candidato_id,
                candidato_nombre=candidato_nombre,
                proceso_id=proceso_id,
                proceso_titulo=proceso_titulo,
                skills=skills,
                experiencia=experiencia,
                preguntas=preguntas,
                duracion_estimada_min=duracion_estimada,
            )

            if "error" in kit_result:
                span.set_attribute("error", kit_result["error"])
                return jsonify({"status": "error", "message": kit_result["error"]}), 500

            port         = int(os.environ.get("ENTREVISTAS_AGENT_PORT", 8003))
            filename     = kit_result.get("filename", "")
            download_url = f"http://localhost:{port}/download/{filename}.docx" if filename else ""

            span.set_attribute("output.preguntas_total", len(preguntas))
            span.set_attribute("output.inflation_score", str(cv_inflado_result.get("inflation_score", "")))
            return jsonify({
                "status":               "ok",
                "candidato_nombre":     candidato_nombre,
                "proceso_id":           proceso_id,
                "kit_path_docx":        kit_result.get("kit_path_docx", ""),
                "kit_download_url":     download_url,
                "preguntas_total":      len(preguntas),
                "duracion_min":         duracion_estimada,
                "email_enviado":        False,
                "guardado_en_supabase": False,
                "inflation_score":      cv_inflado_result.get("inflation_score"),
                "red_flags":            cv_inflado_result.get("red_flags", []),
                "cv_resumen":           cv_inflado_result.get("resumen", ""),
            })

        except Exception as exc:
            logger.exception("Error inesperado en preparar_entrevista")
            span.set_attribute("error", str(exc))
            return jsonify({"status": "error", "message": str(exc)}), 500


if __name__ == "__main__":
    port = int(os.environ.get("ENTREVISTAS_AGENT_PORT", 8003))
    logger.info("Agente Entrevistas en http://localhost:%d/a2a/entrevistas", port)
    app.run(host="0.0.0.0", port=port, debug=False)
