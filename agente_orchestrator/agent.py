"""
Orchestrator root agent — entry point for the A2A recruiting system.

At import time:
  1. The agent registry is loaded (remote card URLs with local fallback).
  2. The system instruction is built (current UTC time + registry summary injected).
  3. The root_agent is instantiated with the single generic tool.

To add a new agent to the system:
  1. Append an entry to orchestrator/registry/registry.json
  2. Add the corresponding env var to .env
  3. (Optional) drop a fallback card under registry/fallback_cards/
  4. Restart the Orchestrator — no Python changes required.
"""

import os
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

from google.adk.agents import LlmAgent
from google.adk.models.lite_llm import LiteLlm

from prompts.orchestrator import build_system_instruction
from registry.loader import get_registry_summary_for_prompt, load_registry
from tools.call_external_agent import call_external_agent

# --- Startup: load registry and build system instruction ---

_registry = load_registry()
_now_utc_iso = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
_tz_name = os.getenv("DEFAULT_TIMEZONE", "America/Argentina/Buenos_Aires")
_now_local_iso = datetime.now(ZoneInfo(_tz_name)).strftime("%Y-%m-%dT%H:%M:%S")
_registry_summary = get_registry_summary_for_prompt(_registry)
_instruction = build_system_instruction(_registry_summary, _now_utc_iso, _tz_name, _now_local_iso)

# --- Agent definition ---

root_agent = LlmAgent(
    name="recruiting_orchestrator",
    model=LiteLlm(model="openai/gpt-4o-mini"),
    description=(
        "Recruiting orchestrator. Delegates tasks to specialized agents "
        "via HTTP, driven by dynamically loaded agent cards."
    ),
    instruction=_instruction,
    tools=[call_external_agent],
)
