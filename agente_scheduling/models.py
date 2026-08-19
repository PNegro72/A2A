"""
Modelos Pydantic v2 para el agente de scheduling.

Definen y validan el payload de las tres acciones expuestas por el agente A2A:
  - propose_slots   -> ProposeRequest
  - confirm_booking -> ConfirmRequest
  - send_email      -> SendEmailRequest

Las ventanas y slots de tiempo se expresan como strings ISO 8601 UTC
(ej: '2026-04-21T14:00:00Z'), siguiendo la convención del agent card.
"""

from pydantic import BaseModel, Field, field_validator


class TimeWindow(BaseModel):
    """Rango temporal en el que buscar disponibilidad."""
    start: str
    end: str


class TimeSlot(BaseModel):
    """Slot concreto elegido para la reunión."""
    start: str
    end: str


class ProposeRequest(BaseModel):
    """Payload de la acción 'propose_slots'.

    `participants` son los INVITADOS (a quienes invitar). El organizador NO va
    en esta lista: se toma de la cuenta autenticada (token.json). Mínimo 1 invitado.
    """
    action: str
    participants: list[str] = Field(..., min_length=1)
    window: TimeWindow
    duration_minutes: float = Field(..., gt=0)

    @field_validator("participants")
    @classmethod
    def _at_least_one_invitee(cls, v: list[str]) -> list[str]:
        if not isinstance(v, list) or len(v) < 1:
            raise ValueError("'participants' must include at least 1 invitee email")
        return v


class SendEmailRequest(BaseModel):
    """Payload de la acción 'send_email'.

    Enviado por el agente de entrevistas para delegar el envío real de un email
    de contacto a un candidato. El scheduling agent lo envía vía Gmail API desde
    la cuenta autenticada (misma cuenta usada para Calendar).
    """
    action: str
    candidato_email: str = Field(..., min_length=1)
    asunto: str = Field(..., min_length=1)
    cuerpo_email: str = Field(..., min_length=1)
    candidato_nombre: str = ""
    proceso_titulo: str = ""
    remitente_email: str | None = None

    @field_validator("candidato_email")
    @classmethod
    def _valid_email_shape(cls, v: str) -> str:
        if "@" not in v:
            raise ValueError("'candidato_email' must be a valid email address")
        return v


class ConfirmRequest(BaseModel):
    """Payload de la acción 'confirm_booking'.

    `participants` son los INVITADOS. El organizador (cuenta autenticada) es el
    dueño del evento y no necesita ir en la lista. Mínimo 1 invitado.
    """
    action: str
    participants: list[str] = Field(..., min_length=1)
    chosen_slot: TimeSlot
    meeting_title: str = Field(..., min_length=1)
    location_or_link: str = ""

    @field_validator("participants")
    @classmethod
    def _at_least_one_invitee(cls, v: list[str]) -> list[str]:
        if not isinstance(v, list) or len(v) < 1:
            raise ValueError("'participants' must include at least 1 invitee email")
        return v
