"""
Generic HTTP tool — the Orchestrator's only tool.

Sends a POST request to any registered agent's webhook URL.
The tool is completely agent-agnostic: it resolves the target URL
from the loaded registry and forwards the payload built by the LLM.
No agent-specific logic lives here.
"""

import logging
import os

import requests
from requests.exceptions import ConnectionError, RequestException, Timeout

from registry.loader import get_registry

logger = logging.getLogger(__name__)

# Timeout para llamadas HTTP a agentes downstream.
# busquedas_internas puede tardar bastante (consulta ATS + ranking LLM con varios candidatos)
# — por eso este valor vive en .env y suele ser >= 120s.
AGENT_HTTP_TIMEOUT = int(os.environ["AGENT_HTTP_TIMEOUT"])


def _parse_timeout_overrides(raw: str) -> dict[str, int]:
    """Parsea ``agente_a:30,agente_b:45`` en ``{"agente_a": 30, "agente_b": 45}``.

    Una entrada mal formada se loguea y se descarta: un override roto tiene que
    degradar al timeout global, no tumbar el arranque del orchestrator.
    """
    overrides: dict[str, int] = {}
    for entry in raw.split(","):
        entry = entry.strip()
        if not entry:
            continue
        name, _, value = entry.partition(":")
        name, value = name.strip(), value.strip()
        if not name or not value.isdigit() or int(value) <= 0:
            logger.warning(
                "AGENT_HTTP_TIMEOUT_OVERRIDES: entrada inválida %r (formato esperado "
                "'agente:segundos'). Se ignora y ese agente usa el timeout global.",
                entry,
            )
            continue
        overrides[name] = int(value)
    return overrides


# Presupuesto de tiempo por agente, para los que tienen que ceder antes que el
# resto. Formato: "agente:segundos,agente:segundos".
#
# Caso de uso: busquedas_externas corre un pipeline de 7 etapas contra APIs de
# terceros y se midió entre 95s y 152s. Darle un presupuesto corto lo convierte
# en una fuente best-effort — si no llega, el orchestrator sigue con los
# candidatos internos en lugar de hacer esperar al reclutador.
#
# Esto NO es lógica agent-specific: el mapa es data de configuración y la tool
# sigue siendo agnóstica de qué agente está llamando.
AGENT_HTTP_TIMEOUT_OVERRIDES = _parse_timeout_overrides(
    os.environ.get("AGENT_HTTP_TIMEOUT_OVERRIDES", "")
)

if AGENT_HTTP_TIMEOUT_OVERRIDES:
    logger.info(
        "Timeouts por agente: %s (global: %ss)",
        AGENT_HTTP_TIMEOUT_OVERRIDES, AGENT_HTTP_TIMEOUT,
    )


def call_external_agent(agent_name: str, payload: dict) -> dict:
    """
    Sends an HTTP POST to the webhook URL of the specified registered agent.

    The agent must exist in the loaded registry. The webhook URL is read
    from the agent's card (field: webhook_url). The payload is sent as
    the JSON body. This tool is agent-agnostic: it works for any agent
    registered in the registry.

    Args:
        agent_name: Name of the target agent. Must match a key in the loaded
            registry (e.g., "scheduling_agent"). Check the registered agents
            section of your instruction for valid names.
        payload: Dictionary to send as the JSON body. Build it strictly
            according to the chosen action's request_schema as described in
            the agent's card. Always include "action" as the first key.

    Returns:
        A dict. On success: the parsed JSON response from the external agent.
        On failure: {"status": "error", "code": "<CODE>", "message": "<details>"}.
        Never raises — always returns a dict.
    """
    registry = get_registry()

    if agent_name not in registry:
        logger.error("Agent '%s' not found in registry. Available: %s", agent_name, list(registry.keys()))
        return {
            "status": "error",
            "code": "AGENT_NOT_FOUND",
            "message": (
                f"No agent named '{agent_name}' is registered. "
                f"Available agents: {list(registry.keys())}"
            ),
        }

    card = registry[agent_name]
    webhook_url = card.get("webhook_url", "").strip()

    if not webhook_url:
        logger.error("Card for '%s' has no webhook_url field.", agent_name)
        return {
            "status": "error",
            "code": "MISSING_WEBHOOK_URL",
            "message": f"Agent '{agent_name}' card does not declare a webhook_url.",
        }

    timeout = AGENT_HTTP_TIMEOUT_OVERRIDES.get(agent_name, AGENT_HTTP_TIMEOUT)

    logger.info(
        "Calling agent '%s' | action: %s | timeout: %ss%s",
        agent_name, payload.get("action"), timeout,
        " (override)" if agent_name in AGENT_HTTP_TIMEOUT_OVERRIDES else "",
    )
    logger.debug("Payload -> %s", payload)

    try:
        response = requests.post(webhook_url, json=payload, timeout=timeout)
        # No usamos raise_for_status() acá porque tira la excepción ANTES de leer el body
        # y los agentes downstream devuelven JSON con `message` aún en 4xx/5xx.
        # Queremos preservar ese mensaje para diagnosticar.
        try:
            result = response.json()
        except ValueError:
            logger.error(
                "Agent '%s' returned non-JSON body (HTTP %s): %s",
                agent_name, response.status_code, response.text[:500],
            )
            return {
                "status": "error",
                "code": "INVALID_JSON_RESPONSE",
                "message": (
                    f"Agent '{agent_name}' returned HTTP {response.status_code} "
                    f"with non-JSON body: {response.text[:200]}"
                ),
            }

        if response.status_code >= 400:
            downstream_msg = result.get("message") if isinstance(result, dict) else None
            logger.error(
                "Agent '%s' returned HTTP %s | downstream message: %s",
                agent_name, response.status_code, downstream_msg,
            )
            return {
                "status": "error",
                "code": "HTTP_ERROR",
                "http_status": response.status_code,
                "message": (
                    f"Agent '{agent_name}' returned HTTP {response.status_code}. "
                    f"Downstream said: {downstream_msg or '(no message)'}"
                ),
            }

        logger.info("Response from '%s' | status: %s", agent_name, result.get("status"))
        logger.debug("Response body <- %s", result)
        return result

    except Timeout:
        presupuestado = agent_name in AGENT_HTTP_TIMEOUT_OVERRIDES
        logger.warning(
            "Timeout calling agent '%s' (%ss exceeded)%s.",
            agent_name, timeout,
            " — presupuesto propio, se sigue sin esta fuente" if presupuestado else "",
        )
        return {
            "status": "error",
            "code": "AGENT_TIMEOUT",
            "degraded": True,
            "message": (
                f"Agent '{agent_name}' did not answer within its {timeout}s time budget. "
                f"Treat it as an unavailable best-effort source: continue with the results "
                f"you already have from the other agents, and tell the user plainly that "
                f"this source was skipped because it exceeded its time budget. "
                f"Do NOT retry it and do NOT invent results for it."
            ),
        }

    except ConnectionError as exc:
        logger.warning("Connection error calling agent '%s': %s", agent_name, exc)
        return {
            "status": "error",
            "code": "NETWORK_ERROR",
            "message": f"Could not connect to agent '{agent_name}': {exc}",
        }

    except RequestException as exc:
        logger.warning("Unexpected request error calling agent '%s': %s", agent_name, exc)
        return {
            "status": "error",
            "code": "NETWORK_ERROR",
            "message": f"Unexpected network error calling '{agent_name}': {exc}",
        }
