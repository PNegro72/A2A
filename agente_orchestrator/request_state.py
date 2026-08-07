"""
Estado en memoria de los requests del orchestrator.

Sirve al endpoint de polling (`GET /chat/status/{request_id}`), que es el
transporte alternativo a SSE cuando un proxy corta el streaming.

Este módulo no depende de ADK ni de FastAPI a propósito: contiene sólo la
máquina de estados, para poder testearla sin levantar el stack completo.
"""

from __future__ import annotations

import logging
import time
from typing import Any, Callable, Literal

logger = logging.getLogger(__name__)

RequestStatus = Literal["running", "done", "error"]

DEFAULT_TTL_SECONDS = 600

# Cota dura para un request que quedó 'running'. Si una corrida se cuelga y su
# task nunca ejecuta el finally, el estado igual se purga pasado este tiempo.
DEFAULT_MAX_RUNNING_SECONDS = 1800

# El frontend deja de pollear cuando el status es 'done' o 'error'. Si el agente
# termina sin emitir una respuesta final, cerramos con este error para que el
# cliente no quede polleando para siempre.
NO_FINAL_RESPONSE_CODE = "NO_FINAL_RESPONSE"
NO_FINAL_RESPONSE_MESSAGE = "El orchestrator no devolvió una respuesta final."


class RequestStateStore:
    """Acumula los eventos de un request para que el cliente los consulte por polling.

    Los pasos se guardan de forma acumulativa: cada snapshot devuelve la lista
    completa y el cliente descarta los que ya vio.
    """

    def __init__(
        self,
        ttl_seconds: int = DEFAULT_TTL_SECONDS,
        clock: Callable[[], float] = time.monotonic,
        max_running_seconds: int = DEFAULT_MAX_RUNNING_SECONDS,
    ) -> None:
        self._states: dict[str, dict[str, Any]] = {}
        self._ttl_seconds = ttl_seconds
        self._max_running_seconds = max_running_seconds
        self._clock = clock

    def start(self, request_id: str) -> None:
        """Registra un request como en curso. Sobrescribe cualquier estado previo."""
        self._states[request_id] = {
            "status": "running",
            "steps": [],
            "final": None,
            "error": None,
            "started_at": self._clock(),
            "finished_at": None,
        }

    def is_tracked(self, request_id: str) -> bool:
        return request_id in self._states

    def add_step(self, request_id: str, step: dict[str, Any]) -> None:
        state = self._get_mutable(request_id, "add_step")
        if state is None:
            return
        state["steps"].append(step)

    def set_final(self, request_id: str, final: dict[str, Any]) -> None:
        state = self._get_mutable(request_id, "set_final")
        if state is None:
            return
        state["final"] = final
        state["status"] = "done"
        state["finished_at"] = self._clock()

    def set_error(self, request_id: str, code: str, message: str) -> None:
        state = self._get_mutable(request_id, "set_error")
        if state is None:
            return
        state["error"] = {"code": code, "message": message}
        state["status"] = "error"
        state["finished_at"] = self._clock()

    def finish(self, request_id: str) -> None:
        """Cierra el request. Si terminó sin respuesta final, lo marca como error."""
        state = self._get_mutable(request_id, "finish")
        if state is None:
            return
        if state["status"] == "running":
            self.set_error(request_id, NO_FINAL_RESPONSE_CODE, NO_FINAL_RESPONSE_MESSAGE)
            return
        state["finished_at"] = self._clock()

    def snapshot(self, request_id: str) -> dict[str, Any] | None:
        """Devuelve una copia del estado, o None si el request no está registrado."""
        state = self._states.get(request_id)
        if state is None:
            return None
        return {
            "status": state["status"],
            "steps": list(state["steps"]),
            "final": state["final"],
            "error": state["error"],
        }

    def purge_expired(self) -> int:
        """Elimina estados vencidos: terminados pasado el TTL, o colgados en 'running'.

        Devuelve cuántos borró.
        """
        now = self._clock()
        expired = [
            request_id
            for request_id, state in self._states.items()
            if self._is_expired(state, now)
        ]
        for request_id in expired:
            del self._states[request_id]
        if expired:
            logger.info("Purgados %d estados de request vencidos", len(expired))
        return len(expired)

    def _is_expired(self, state: dict[str, Any], now: float) -> bool:
        if state["finished_at"] is not None:
            return now - state["finished_at"] > self._ttl_seconds
        return now - state["started_at"] > self._max_running_seconds

    def __len__(self) -> int:
        return len(self._states)

    def _get_mutable(self, request_id: str, operation: str) -> dict[str, Any] | None:
        state = self._states.get(request_id)
        if state is None:
            logger.warning("%s sobre request_id desconocido: %s", operation, request_id)
        return state
