"""
Tool: crear_borrador_email
Envía el email al candidato delegando el envío al agente de scheduling.

La lógica real de transporte ya no vive en este agente.
"""

import os

import requests


def crear_borrador_email(
    candidato_nombre: str,
    candidato_email: str,
    proceso_titulo: str,
    cuerpo_email: str,
    remitente_email: str | None = None,
    asunto: str | None = None,
) -> dict:
    """
    Envía el email delegando la operación al agente de scheduling.

    Args:
        candidato_nombre: Nombre completo del candidato.
        candidato_email: Email del candidato destinatario.
        proceso_titulo: Título del proceso/posición (para el asunto).
        cuerpo_email: Cuerpo del email en HTML o texto plano.
        remitente_email: Email remitente. Si es None, el agente usa el remitente configurado.
        asunto: Asunto del email. Si es None, se genera automáticamente.

    Returns:
        Dict con status del envío y metadata.
    """
    scheduling_url = os.environ.get("SCHEDULING_AGENT_URL", "http://localhost:8004/scheduling-agent")
    subject = asunto or f"Oportunidad laboral: {proceso_titulo}"
    payload = {
        "action": "send_email",
        "candidato_nombre": candidato_nombre,
        "candidato_email": candidato_email,
        "proceso_titulo": proceso_titulo,
        "cuerpo_email": cuerpo_email,
        "remitente_email": remitente_email,
        "asunto": subject,
    }

    try:
        response = requests.post(scheduling_url, json=payload, timeout=30)
        data = response.json() if response.content else {}
    except Exception as exc:
        return {
            "error": f"Error llamando al agente scheduling: {exc}",
            "draft_id": None,
        }

    if response.status_code >= 400:
        return {
            "error": data.get("message") or "Error enviando email desde el agente scheduling.",
            "draft_id": None,
        }

    if data.get("status") in {"ok", "enviado"} or data.get("email_enviado"):
        success_message = data.get("mensaje") or f"Email enviado correctamente a {candidato_email} via scheduling agent."
        if candidato_email not in success_message:
            success_message = f"Email enviado correctamente a {candidato_email}. {success_message}"

        response_asunto = data.get("asunto") or subject
        if asunto is not None:
            response_asunto = asunto

        return {
            "status": "enviado",
            "draft_id": None,
            "remitente": data.get("remitente") or remitente_email or os.environ.get("MS_SENDER_EMAIL"),
            "destinatario": candidato_email,
            "asunto": response_asunto,
            "mensaje": success_message,
            "response": data,
        }

    return {
        "error": data.get("message") or "El agente scheduling rechazó el envío del email.",
        "draft_id": None,
    }