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
# busquedas_internas puede tardar bastante (consulta ATS + ranking LLM con varios candidatos),
# así que 120s es razonable. Override con env var AGENT_HTTP_TIMEOUT si hace falta.
AGENT_HTTP_TIMEOUT = int(os.getenv("AGENT_HTTP_TIMEOUT", "120"))


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

    logger.info("Calling agent '%s' | action: %s", agent_name, payload.get("action"))
    logger.debug("Payload -> %s", payload)

    try:
        response = requests.post(webhook_url, json=payload, timeout=AGENT_HTTP_TIMEOUT)
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
        logger.warning("Timeout calling agent '%s' (%ss exceeded).", agent_name, AGENT_HTTP_TIMEOUT)
        return {
            "status": "error",
            "code": "NETWORK_ERROR",
            "message": f"Request to '{agent_name}' timed out after {AGENT_HTTP_TIMEOUT} seconds.",
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
