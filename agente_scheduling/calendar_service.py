"""
Wrapper de Google Calendar API + Gmail API con OAuth2 para el agente de scheduling.

Reemplaza los nodos de n8n `get_calendar_availability` y `create_calendar_event`
por llamadas directas a la API de Google Calendar (gratuita), y además envía los
emails de contacto a candidatos (delegados por el agente de entrevistas) vía
Gmail API, reutilizando las mismas credenciales OAuth2:

  - get_credentials():  carga/refresca el token OAuth2 (token.json), o lo genera
                        de forma interactiva a partir de credentials.json.
  - get_freebusy():     consulta la disponibilidad (freebusy) de los participantes
                        y devuelve los bloques ocupados unificados y fusionados.
  - create_event():     crea un evento con invitados y link de Google Meet.
  - send_email():       envía un email desde la cuenta autenticada vía Gmail API.

Variables de entorno:
  GOOGLE_CREDENTIALS_FILE  ruta al credentials.json (default: credentials.json)
  GOOGLE_TOKEN_FILE        ruta al token.json       (default: token.json)

Nota: agregar el scope de Gmail a un token.json generado antes de esta feature
invalida su alcance — hay que volver a correr `setup_oauth.py` para reautorizar.
"""

import base64
import os
import uuid
from email.mime.text import MIMEText

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build

SCOPES = [
    "https://www.googleapis.com/auth/calendar",
    "https://www.googleapis.com/auth/gmail.send",
]


def _credentials_file() -> str:
    return os.environ.get("GOOGLE_CREDENTIALS_FILE", "credentials.json")


def _token_file() -> str:
    return os.environ.get("GOOGLE_TOKEN_FILE", "token.json")


def get_credentials() -> Credentials:
    """
    Devuelve credenciales OAuth2 válidas.

    Carga token.json si existe. Si está expirado pero tiene refresh_token, lo
    refresca. Si no existe (o no se puede refrescar), lanza el flujo OAuth2
    interactivo usando credentials.json y persiste el nuevo token.
    """
    token_path = _token_file()
    creds: Credentials | None = None

    if os.path.exists(token_path):
        creds = Credentials.from_authorized_user_file(token_path, SCOPES)

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(_credentials_file(), SCOPES)
            creds = flow.run_local_server(port=0)

        with open(token_path, "w", encoding="utf-8") as token:
            token.write(creds.to_json())

    return creds


def _build_service():
    return build("calendar", "v3", credentials=get_credentials(), cache_discovery=False)


def _build_gmail_service():
    return build("gmail", "v1", credentials=get_credentials(), cache_discovery=False)


def get_organizer_email() -> str:
    """Email del organizador = dueño del calendario primario de la cuenta autenticada."""
    service = _build_service()
    return service.calendars().get(calendarId="primary").execute()["id"]


def _to_ms(iso_ts: str) -> int:
    """Convierte un timestamp ISO 8601 (con sufijo Z o offset) a epoch ms."""
    from datetime import datetime

    normalized = iso_ts.replace("Z", "+00:00")
    return int(datetime.fromisoformat(normalized).timestamp() * 1000)


def get_freebusy(participants: list[str], window_start: str, window_end: str) -> list[dict]:
    """
    Consulta la disponibilidad del organizador + los invitados en la ventana dada.

    `participants` son los invitados. Se agrega "primary" (el calendario del
    organizador autenticado) para que los slots propuestos contemplen también su
    agenda. Llama a calendar.freebusy().query() con todos como items, unifica los
    bloques ocupados, los ordena por inicio y fusiona los solapados.

    Retorna una lista de {"start": epoch_ms, "end": epoch_ms} ordenada y sin solapes.
    """
    service = _build_service()

    # "primary" = organizador (cuenta autenticada); el resto son los invitados.
    calendar_ids = ["primary"] + list(participants)
    body = {
        "timeMin": window_start,
        "timeMax": window_end,
        "items": [{"id": cal_id} for cal_id in calendar_ids],
    }
    response = service.freebusy().query(body=body).execute()

    # Unificar todos los bloques ocupados de todos los participantes
    busy_blocks: list[dict] = []
    for cal in response.get("calendars", {}).values():
        for period in cal.get("busy", []):
            busy_blocks.append({
                "start": _to_ms(period["start"]),
                "end": _to_ms(period["end"]),
            })

    busy_blocks.sort(key=lambda b: b["start"])

    # Fusionar bloques solapados
    merged: list[dict] = []
    for block in busy_blocks:
        if not merged or block["start"] > merged[-1]["end"]:
            merged.append(dict(block))
        else:
            merged[-1]["end"] = max(merged[-1]["end"], block["end"])

    return merged


def create_event(
    participants: list[str],
    chosen_slot: dict,
    meeting_title: str,
    location_or_link: str = "",
) -> dict:
    """
    Crea un evento en el calendario del usuario autenticado (primary), que queda
    como organizador del evento.

    `participants` son los invitados: se agregan como attendees. Se solicita un
    link de Google Meet vía conferenceData. Envía notificaciones (sendUpdates=all).

    Retorna el evento creado por la API (incluye id, htmlLink, hangoutLink,
    summary, start, end).
    """
    service = _build_service()

    event_body = {
        "summary": meeting_title,
        "start": {"dateTime": chosen_slot["start"]},
        "end": {"dateTime": chosen_slot["end"]},
        "attendees": [{"email": email} for email in participants],
        "conferenceData": {
            "createRequest": {
                "requestId": str(uuid.uuid4()),
                "conferenceSolutionKey": {"type": "hangoutsMeet"},
            }
        },
    }
    if location_or_link:
        event_body["location"] = location_or_link

    return (
        service.events()
        .insert(
            calendarId="primary",
            body=event_body,
            sendUpdates="all",
            conferenceDataVersion=1,
        )
        .execute()
    )


def send_email(to: str, subject: str, body: str) -> dict:
    """
    Envía un email vía Gmail API desde la cuenta autenticada (misma cuenta que
    Calendar). Gmail siempre usa esa cuenta como remitente real: no soporta un
    "From" arbitrario sin delegación de dominio, así que no se acepta remitente.

    Detecta HTML vs texto plano mirando si `body` arranca con '<'.

    Retorna el mensaje creado por la API (incluye al menos "id").
    """
    service = _build_gmail_service()

    is_html = body.strip().startswith("<")
    message = MIMEText(body, "html" if is_html else "plain", "utf-8")
    message["to"] = to
    message["subject"] = subject

    raw = base64.urlsafe_b64encode(message.as_bytes()).decode("utf-8")

    return service.users().messages().send(userId="me", body={"raw": raw}).execute()
