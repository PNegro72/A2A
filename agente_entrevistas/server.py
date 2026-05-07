"""
server.py — HTTP server para el Agente Entrevistas.
El orquestador lo llama via POST http://localhost:8003/a2a/entrevistas
 
Correr desde la carpeta agente_entrevistas/:
    python server.py
"""
 
import logging
import os
import sys
from pathlib import Path
 
sys.path.insert(0, str(Path(__file__).parent))
 
from dotenv import load_dotenv
from flask import Flask, jsonify, request, send_file
from flask_cors import CORS
 
load_dotenv()
 
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)
 
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
 
 
def _enviar_email(body: dict):
    """Acción independiente: solo redacta y manda el email, sin regenerar el kit."""
    candidato_nombre = body.get("candidato_nombre", "")
    candidato_email  = body.get("candidato_email", "")
    proceso_titulo   = body.get("proceso_titulo", "")
    skills_clave     = body.get("skills_clave", [])
 
    if not candidato_email:
        return jsonify({"status": "error", "message": "candidato_email es requerido."}), 400
 
    logger.info("Enviando email | candidato=%s email=%s", candidato_nombre, candidato_email)
 
    try:
        from tools.redactar_email import redactar_email
        email_result = redactar_email(
            candidato_nombre=candidato_nombre,
            proceso_titulo=proceso_titulo,
            skills_clave=skills_clave[:4],
        )
 
        if "error" in email_result:
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
            return jsonify({
                "status":        "ok",
                "email_enviado": True,
                "asunto":        send_result.get("asunto"),
                "destinatario":  candidato_email,
            })
        else:
            return jsonify({
                "status":  "error",
                "message": send_result.get("error", "Error enviando email"),
            }), 500
 
    except Exception as exc:
        logger.exception("Error en _enviar_email")
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
    cv_texto         = candidato.get("cv_texto")
    proceso_titulo   = candidato.get("proceso_titulo", "")
 
    logger.info("Preparando entrevista | candidato=%s proceso=%s", candidato_id, proceso_id)
 
    try:
        # 1. Web search
        from tools.web_search import web_search
 
        info_publica = ""
        query = f"{candidato_nombre} software engineer"
        if candidato.get("linkedin_url"):
            query = f"{candidato_nombre} {candidato['linkedin_url']}"
        elif candidato.get("github_username"):
            query = f"{candidato_nombre} github {candidato['github_username']}"
 
        search_result = web_search(query, max_results=5)
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
 
        # 2. Generar preguntas
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
            return jsonify({"status": "error", "message": preguntas_result["error"]}), 500
 
        preguntas         = preguntas_result.get("preguntas", [])
        duracion_estimada = preguntas_result.get("duracion_estimada_min")
 
        # 3. Generar kit
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
            return jsonify({"status": "error", "message": kit_result["error"]}), 500
 
        port         = int(os.environ.get("ENTREVISTAS_AGENT_PORT", 8003))
        filename     = kit_result.get("filename", "")
        download_url = f"http://localhost:{port}/download/{filename}.docx" if filename else ""
 
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
        })
 
    except Exception as exc:
        logger.exception("Error inesperado en preparar_entrevista")
        return jsonify({"status": "error", "message": str(exc)}), 500
 
 
if __name__ == "__main__":
    port = int(os.environ.get("ENTREVISTAS_AGENT_PORT", 8003))
    logger.info("Agente Entrevistas en http://localhost:%d/a2a/entrevistas", port)
    app.run(host="0.0.0.0", port=port, debug=False)
 