"""
Generic HTTP tool — the Orchestrator's only tool.

Sends a POST request to any registered agent's webhook URL.
The tool is completely agent-agnostic: it resolves the target URL
from the loaded registry and forwards the payload built by the LLM.
No agent-specific logic lives here.
"""

import logging

import requests
from requests.exceptions import ConnectionError, RequestException, Timeout

from registry.loader import get_registry

logger = logging.getLogger(__name__)


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
        response = requests.post(webhook_url, json=payload, timeout=30)
        response.raise_for_status()
        result = response.json()
        logger.info("Response from '%s' | status: %s", agent_name, result.get("status"))
        logger.debug("Response body <- %s", result)
        return result

    except Timeout:
        logger.warning("Timeout calling agent '%s' (30s exceeded).", agent_name)
        return {
            "status": "error",
            "code": "NETWORK_ERROR",
            "message": f"Request to '{agent_name}' timed out after 30 seconds.",
        }

    except ConnectionError as exc:
        logger.warning("Connection error calling agent '%s': %s", agent_name, exc)
        return {
            "status": "error",
            "code": "NETWORK_ERROR",
            "message": f"Could not connect to agent '{agent_name}': {exc}",
        }

    except requests.HTTPError as exc:
        status_code = (
            exc.response.status_code if exc.response is not None else "unknown"
        )
        logger.warning("HTTP %s from agent '%s'.", status_code, agent_name)
        return {
            "status": "error",
            "code": "HTTP_ERROR",
            "message": f"Agent '{agent_name}' returned HTTP {status_code}: {exc}",
        }

    except (ValueError, KeyError) as exc:
        logger.warning("Invalid JSON response from agent '%s': %s", agent_name, exc)
        return {
            "status": "error",
            "code": "INVALID_JSON_RESPONSE",
            "message": f"Agent '{agent_name}' returned a non-JSON response: {exc}",
        }

    except RequestException as exc:
        logger.warning("Unexpected request error calling agent '%s': %s", agent_name, exc)
        return {
            "status": "error",
            "code": "NETWORK_ERROR",
            "message": f"Unexpected network error calling '{agent_name}': {exc}",
        }
