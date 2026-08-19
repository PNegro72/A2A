"""
Servidor HTTP (Flask) para el agente de scheduling.

Reemplaza el workflow de n8n (scheduling-agent-json.json) por una implementación
real en Python sobre Google Calendar API (OAuth2). Mantiene exactamente la misma
interfaz A2A que exponía n8n.

Endpoints:
    POST /scheduling-agent        -> switch por body.action (propose_slots | confirm_booking | send_email)
    GET  /scheduling-agent-card   -> agent card JSON (webhook_url -> local)
    GET  /health                  -> healthcheck

Acciones (POST /scheduling-agent):
    propose_slots    consulta freebusy de los participantes y propone hasta 5 slots libres
    confirm_booking  crea el evento con link de Google Meet e invita a los participantes
    send_email       envía un email de contacto a un candidato vía Gmail API (usado por el
                     agente de entrevistas, que delega toda la lógica de transporte acá)

Correr con (desde la carpeta agente_scheduling/):
    python server.py
"""

import logging
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from dotenv import load_dotenv

load_dotenv(override=True)

from flask import Flask, jsonify, request  # noqa: E402
from flask_cors import CORS  # noqa: E402
from pydantic import ValidationError  # noqa: E402

import calendar_service  # noqa: E402
from models import ConfirmRequest, ProposeRequest, SendEmailRequest  # noqa: E402

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)

app = Flask(__name__)
CORS(app)


# ──────────────────────────────────────────────────────────────────────────────
# Agent card — idéntico al fallback card, con webhook_url apuntando al agente local
# ──────────────────────────────────────────────────────────────────────────────
AGENT_CARD = {
    "name": "scheduling_agent",
    "version": "1.0.0",
    "description": (
        "Schedules meetings and interviews. Queries participants' Google Calendar "
        "availability, proposes free slots within a given time window, and creates "
        "confirmed events with an auto-generated Google Meet link. Also sends candidate "
        "contact emails via Gmail API on behalf of the interview agent. All datetimes in UTC."
    ),
    "when_to_use": (
        "When the user wants to schedule, book, arrange, check availability for, or "
        "confirm a meeting, interview, call, or calendar event — or when a candidate "
        "contact email needs to be sent."
    ),
    "webhook_url": "http://localhost:8004/scheduling-agent",
    "http_method": "POST",
    "actions": [
        {
            "name": "propose_slots",
            "description": (
                "Finds free time slots in the participants' calendars within a given "
                "window and returns up to 5 available slots of the requested duration. "
                "Use this when the user did NOT provide an exact date and time, but "
                "rather a range (e.g., 'next week', 'tomorrow afternoon')."
            ),
            "request_schema": {
                "action": "propose_slots",
                "participants": ["invitee@example.com"],
                "window": {"start": "ISO8601 UTC", "end": "ISO8601 UTC"},
                "duration_minutes": "number > 0",
            },
            "possible_responses": [
                {"status": "slots_proposed", "fields": ["slots[]", "participants", "window", "duration_minutes"]},
                {"status": "no_slots_available", "fields": ["window_checked"]},
                {"status": "error", "fields": ["code", "errors"]},
            ],
        },
        {
            "name": "confirm_booking",
            "description": (
                "Creates an event in the scheduling account's calendar (the organizer) "
                "and invites the participants. Automatically generates a Google Meet "
                "link. Use this when the user has already chosen a specific slot, either "
                "by requesting it directly or by selecting one of the slots previously "
                "proposed by 'propose_slots'."
            ),
            "request_schema": {
                "action": "confirm_booking",
                "participants": ["invitee@example.com"],
                "chosen_slot": {"start": "ISO8601 UTC", "end": "ISO8601 UTC"},
                "meeting_title": "string",
                "location_or_link": "string (optional)",
            },
            "possible_responses": [
                {"status": "meeting_confirmed", "fields": ["event_id", "event_link", "meet_link", "summary", "start", "end"]},
                {"status": "error", "fields": ["code", "phase", "message"]},
            ],
        },
        {
            "name": "send_email",
            "description": (
                "Sends a contact email to a candidate via Gmail API, from the "
                "scheduling account's authenticated Gmail address. Used by the "
                "interview agent (agente_entrevistas) to delegate the actual "
                "email transport, instead of sending it directly."
            ),
            "request_schema": {
                "action": "send_email",
                "candidato_email": "candidate@example.com",
                "asunto": "string",
                "cuerpo_email": "string (plain text or HTML)",
                "candidato_nombre": "string (optional, for logging only)",
                "proceso_titulo": "string (optional, for logging only)",
                "remitente_email": "string (optional, ignored — Gmail always sends from the authenticated account)",
            },
            "possible_responses": [
                {"status": "enviado", "fields": ["message_id", "remitente", "destinatario", "asunto", "mensaje"]},
                {"status": "error", "fields": ["code", "message"]},
            ],
        },
    ],
    "conventions": {
        "datetime_format": "ISO 8601 UTC with Z suffix (e.g., '2026-04-21T14:00:00Z')",
        "participants_rules": (
            "Array of INVITEE emails, minimum 1. The organizer is the authenticated "
            "scheduling account and is added automatically — do NOT include it in this "
            "list. Never fabricate or guess emails: only include addresses the user "
            "explicitly provided. If no invitee email is known, ask the user for it."
        ),
        "state": (
            "Stateless: each request is independent. The orchestrator must remember "
            "previously proposed slots in order to map user references like 'the second "
            "one' to a concrete slot."
        ),
    },
}


# ──────────────────────────────────────────────────────────────────────────────
# Helpers de tiempo + cálculo de slots (traducido del JS de n8n compute_available_slots)
# ──────────────────────────────────────────────────────────────────────────────
def parse_iso_to_ms(iso_ts: str) -> int:
    normalized = iso_ts.replace("Z", "+00:00")
    return int(datetime.fromisoformat(normalized).timestamp() * 1000)


def ms_to_iso(ms: int) -> str:
    dt = datetime.fromtimestamp(ms / 1000, tz=timezone.utc)
    return dt.strftime("%Y-%m-%dT%H:%M:%SZ")


def compute_available_slots(busy_blocks, window_start_iso, window_end_iso, duration_minutes, max_slots=5):
    """
    Calcula hasta `max_slots` huecos libres de `duration_minutes` en la ventana.

    `busy_blocks` deben venir ya ordenados y fusionados (get_freebusy() los entrega así).
    """
    window_start = parse_iso_to_ms(window_start_iso)
    window_end = parse_iso_to_ms(window_end_iso)
    duration_ms = duration_minutes * 60 * 1000

    slots = []
    cursor = window_start

    for block in busy_blocks:
        if len(slots) >= max_slots:
            break
        if block["start"] > cursor and (block["start"] - cursor) >= duration_ms:
            slots.append({
                "start": ms_to_iso(cursor),
                "end": ms_to_iso(int(cursor + duration_ms)),
            })
        cursor = max(cursor, block["end"])

    # Hueco final después del último bloque ocupado
    if len(slots) < max_slots and (window_end - cursor) >= duration_ms:
        slots.append({
            "start": ms_to_iso(cursor),
            "end": ms_to_iso(int(cursor + duration_ms)),
        })

    return slots[:max_slots]


# ──────────────────────────────────────────────────────────────────────────────
# Endpoints
# ──────────────────────────────────────────────────────────────────────────────
@app.route("/scheduling-agent", methods=["POST"])
def scheduling_agent():
    body = request.get_json(silent=True) or {}
    action = body.get("action")

    if action == "propose_slots":
        return _propose_slots(body)

    if action == "confirm_booking":
        return _confirm_booking(body)

    if action == "send_email":
        return _send_email(body)

    return jsonify({"status": "error", "code": "UNKNOWN_ACTION"})


@app.route("/scheduling-agent-card", methods=["GET"])
def scheduling_agent_card():
    return jsonify(AGENT_CARD)


@app.route("/health", methods=["GET"])
def health():
    return jsonify({"status": "ok", "agent": "scheduling_agent"})


# ──────────────────────────────────────────────────────────────────────────────
# Acciones
# ──────────────────────────────────────────────────────────────────────────────
def _propose_slots(body: dict):
    try:
        req = ProposeRequest(**body)
    except ValidationError as exc:
        return jsonify({
            "status": "error",
            "code": "INVALID_PAYLOAD",
            "errors": _format_errors(exc),
        }), 400

    logger.info(
        "propose_slots | participants=%d window=%s..%s dur=%s",
        len(req.participants), req.window.start, req.window.end, req.duration_minutes,
    )

    try:
        busy_blocks = calendar_service.get_freebusy(
            req.participants, req.window.start, req.window.end
        )
    except Exception as exc:
        logger.exception("Error consultando freebusy")
        return jsonify({
            "status": "error",
            "code": "CALENDAR_API_ERROR",
            "phase": "fetch_availability",
            "message": f"Failed to fetch calendar availability: {exc}",
        }), 500

    slots = compute_available_slots(
        busy_blocks, req.window.start, req.window.end, req.duration_minutes
    )

    if not slots:
        return jsonify({
            "status": "no_slots_available",
            "window_checked": {"start": req.window.start, "end": req.window.end},
        })

    return jsonify({
        "status": "slots_proposed",
        "slots": slots,
        "participants": req.participants,
        "window": {"start": req.window.start, "end": req.window.end},
        "duration_minutes": req.duration_minutes,
    })


def _confirm_booking(body: dict):
    try:
        req = ConfirmRequest(**body)
    except ValidationError as exc:
        return jsonify({
            "status": "error",
            "code": "INVALID_PAYLOAD",
            "errors": _format_errors(exc),
        }), 400

    logger.info(
        "confirm_booking | participants=%d slot=%s..%s title=%s",
        len(req.participants), req.chosen_slot.start, req.chosen_slot.end, req.meeting_title,
    )

    try:
        event = calendar_service.create_event(
            participants=req.participants,
            chosen_slot={"start": req.chosen_slot.start, "end": req.chosen_slot.end},
            meeting_title=req.meeting_title,
            location_or_link=req.location_or_link,
        )
    except Exception as exc:
        logger.exception("Error creando evento")
        return jsonify({
            "status": "error",
            "code": "CALENDAR_API_ERROR",
            "phase": "create_event",
            "message": f"Failed to create the event in Google Calendar: {exc}",
        }), 500

    return jsonify({
        "status": "meeting_confirmed",
        "event_id": event.get("id", ""),
        "event_link": event.get("htmlLink", ""),
        "meet_link": event.get("hangoutLink", ""),
        "summary": event.get("summary", ""),
        "start": event.get("start", {}).get("dateTime", ""),
        "end": event.get("end", {}).get("dateTime", ""),
    })


def _send_email(body: dict):
    try:
        req = SendEmailRequest(**body)
    except ValidationError as exc:
        return jsonify({
            "status": "error",
            "code": "INVALID_PAYLOAD",
            "message": _format_errors(exc),
        }), 400

    logger.info(
        "send_email | to=%s asunto=%s proceso=%s",
        req.candidato_email, req.asunto, req.proceso_titulo,
    )

    try:
        organizer = calendar_service.get_organizer_email()
        result = calendar_service.send_email(
            to=req.candidato_email,
            subject=req.asunto,
            body=req.cuerpo_email,
        )
    except Exception as exc:
        logger.exception("Error enviando email vía Gmail")
        return jsonify({
            "status": "error",
            "code": "GMAIL_API_ERROR",
            "message": f"Failed to send email via Gmail: {exc}",
        }), 500

    return jsonify({
        "status": "enviado",
        "message_id": result.get("id", ""),
        "remitente": organizer,
        "destinatario": req.candidato_email,
        "asunto": req.asunto,
        "mensaje": f"Email enviado correctamente a {req.candidato_email} via Gmail ({organizer}).",
    })


def _format_errors(exc: ValidationError) -> str:
    """Aplana los errores de Pydantic a un string separado por comas (estilo n8n)."""
    parts = []
    for err in exc.errors():
        loc = ".".join(str(p) for p in err["loc"])
        parts.append(f"{loc}: {err['msg']}")
    return ", ".join(parts)


if __name__ == "__main__":
    port = int(os.environ.get("SCHEDULING_AGENT_PORT", 8004))
    logger.info("Agente Scheduling en http://localhost:%d/scheduling-agent", port)
    app.run(host="0.0.0.0", port=port, debug=False)
