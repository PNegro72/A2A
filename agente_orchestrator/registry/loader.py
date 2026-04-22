"""
Registry loader — fetches and caches agent cards at application startup.

Card source priority per agent:
  1. Remote URL declared in the env var named by `card_url_env`.
  2. Local fallback JSON file at registry/fallback_cards/<name>.json.

The loaded registry is stored in a module-level dict (_REGISTRY) and
exposed via get_registry(). The call_external_agent tool reads from it
at call time without re-fetching.
"""

import json
import logging
import os
from pathlib import Path
from typing import Optional

import requests

logger = logging.getLogger(__name__)

_REGISTRY_JSON = Path(__file__).parent / "registry.json"
_REGISTRY: dict[str, dict] = {}


def load_registry() -> dict[str, dict]:
    """
    Reads registry.json, loads each agent card from its configured source,
    and caches the results in the module-level _REGISTRY dict.

    Returns the populated registry dict keyed by agent name.
    """
    global _REGISTRY

    try:
        with open(_REGISTRY_JSON, encoding="utf-8") as f:
            config = json.load(f)
    except FileNotFoundError:
        logger.error("registry.json not found at: %s", _REGISTRY_JSON)
        return {}
    except json.JSONDecodeError as exc:
        logger.error("registry.json contains invalid JSON: %s", exc)
        return {}

    result: dict[str, dict] = {}

    for entry in config.get("agents", []):
        name = entry.get("name")
        if not name:
            logger.warning("Registry entry missing 'name' field — skipping: %s", entry)
            continue

        card = _load_card(entry, name)
        if card is not None:
            result[name] = card
        else:
            logger.error(
                "Could not load card for agent '%s' from any source — agent will be unavailable.",
                name,
            )

    _REGISTRY = result
    return result


def get_registry() -> dict[str, dict]:
    """Returns the cached registry. Requires load_registry() to have been called first."""
    return _REGISTRY


def _load_card(entry: dict, name: str) -> Optional[dict]:
    """Tries remote URL first, then local fallback. Returns card dict or None."""
    url_env = entry.get("card_url_env", "")
    url = os.environ.get(url_env, "").strip() if url_env else ""

    if url:
        card = _fetch_from_url(url, name)
        if card is not None:
            return card
        logger.warning(
            "Card for '%s' could not be loaded from URL — trying local fallback.", name
        )
    elif url_env:
        logger.warning(
            "Env var '%s' is not set — skipping URL fetch for '%s', trying fallback.",
            url_env,
            name,
        )

    fallback_rel = entry.get("fallback_path", "")
    if fallback_rel:
        return _load_from_file(Path(__file__).parent / fallback_rel, name)

    return None


def _fetch_from_url(url: str, name: str) -> Optional[dict]:
    try:
        resp = requests.get(url, timeout=10)
        resp.raise_for_status()
        card = resp.json()
        logger.info("Loaded card for '%s' from URL: %s", name, url)
        return card
    except requests.exceptions.Timeout:
        logger.warning("Timeout fetching card for '%s' from: %s", name, url)
    except requests.exceptions.ConnectionError as exc:
        logger.warning("Connection error fetching card for '%s': %s", name, exc)
    except requests.exceptions.HTTPError as exc:
        logger.warning(
            "HTTP error fetching card for '%s': %s returned %s",
            name,
            url,
            exc.response.status_code if exc.response is not None else "unknown",
        )
    except (ValueError, KeyError):
        logger.warning("Invalid JSON in card response for '%s' from URL: %s", name, url)
    return None


def _load_from_file(path: Path, name: str) -> Optional[dict]:
    try:
        with open(path, encoding="utf-8") as f:
            card = json.load(f)
        logger.info("Loaded card for '%s' from fallback file: %s", name, path)
        return card
    except FileNotFoundError:
        logger.warning("Fallback file not found for '%s': %s", name, path)
    except json.JSONDecodeError as exc:
        logger.warning(
            "Invalid JSON in fallback file for '%s' at %s: %s", name, path, exc
        )
    return None


def get_registry_summary_for_prompt(registry: dict[str, dict]) -> str:
    """
    Formats loaded agent cards as structured markdown for injection into
    the Orchestrator's system instruction.

    The LLM uses this text to understand what agents are available,
    when to use each one, and how to build the correct payload per action.
    """
    if not registry:
        return "No agents are currently registered. Inform the user that no specialized agents are available."

    sections: list[str] = []

    for name, card in registry.items():
        lines: list[str] = [f"## Agent: `{name}`"]

        if desc := card.get("description"):
            lines.append(f"\n**Description:** {desc}")

        if when := card.get("when_to_use"):
            lines.append(f"\n**When to use:** {when}")

        method = card.get("http_method", "POST")
        webhook = card.get("webhook_url", "")
        if webhook:
            lines.append(f"\n**Endpoint:** `{method} {webhook}`")

        actions: list[dict] = card.get("actions", [])
        if actions:
            lines.append("\n### Actions")
            for action in actions:
                action_name = action.get("name", "unknown")
                action_desc = action.get("description", "")
                lines.append(f"\n#### `{action_name}`")
                if action_desc:
                    lines.append(action_desc)

                schema = action.get("request_schema")
                if schema:
                    schema_str = json.dumps(schema, indent=2)
                    lines.append(f"\nRequest schema:\n```json\n{schema_str}\n```")

                responses: list[dict] = action.get("possible_responses", [])
                if responses:
                    lines.append("\nPossible responses:")
                    for r in responses:
                        status = r.get("status", "unknown")
                        fields = r.get("fields", [])
                        lines.append(f"- `{status}` — fields: {fields}")

        conventions: dict = card.get("conventions", {})
        if conventions:
            lines.append("\n### Conventions")
            for key, value in conventions.items():
                lines.append(f"- **{key}:** {value}")

        sections.append("\n".join(lines))

    return "\n\n---\n\n".join(sections)
