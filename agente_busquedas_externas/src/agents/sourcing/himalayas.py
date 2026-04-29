from google.adk.agents import LlmAgent
from google.adk.tools.mcp_tool.mcp_toolset import McpToolset, SseConnectionParams

from src.domain.models import StateKeys

_HIMALAYAS_MCP_URL = "https://mcp.himalayas.app/mcp"

_INSTRUCTION = (
    "You are a talent sourcing specialist.\n"
    f"Read state['{StateKeys.SEARCH_PLAN}'] to get the Himalayas source query.\n"
    "Use the search_talent tool with parameters from the plan (skills, remote flag, location).\n"
    "For each result, use get_talent_profile to get the full profile.\n"
    "Construct a CandidateLead for each candidate with:\n"
    "  - source='himalayas', source_type='opt-in', verified=True\n"
    "  - evidence entries for: name, headline, current_role, skills, github_url (if present)\n"
    f"Write the JSON list of CandidateLead dicts to state['{StateKeys.LEADS_HIMALAYAS}'].\n"
    "If no candidates match, write an empty list. "
    "Never fabricate candidate data — only use what the tools return."
)


def make_himalayas_source_agent() -> LlmAgent:
    return LlmAgent(
        name="himalayas_source_agent",
        model="gemini-2.0-flash",
        instruction=_INSTRUCTION,
        tools=[McpToolset(connection_params=SseConnectionParams(url=_HIMALAYAS_MCP_URL))],
        output_key=StateKeys.LEADS_HIMALAYAS,
    )


# Module-level singleton for direct use and unit testing
himalayas_source_agent = make_himalayas_source_agent()
