from google.adk.agents import LlmAgent
from google.adk.tools.mcp_tool.mcp_toolset import McpToolset
from google.adk.tools.mcp_tool.mcp_session_manager import StreamableHTTPConnectionParams

from src.config import OPENAI_MODEL
from src.domain.models import StateKeys

_HIMALAYAS_MCP_URL = "https://mcp.himalayas.app/mcp"

_INSTRUCTION = (
    "You are a talent sourcing specialist.\n"
    f"Read state['{StateKeys.SEARCH_PLAN}'] to get the Himalayas source query.\n"
    "Use the search_talent tool with parameters from the plan (skills, remote flag, location).\n"
    "For each result, use get_talent_profile to get the full profile.\n\n"
    "Build a CandidateLead dict for each candidate with EXACTLY these fields:\n"
    '  - "source": "himalayas"\n'
    '  - "raw_id": the candidate ID from Himalayas (e.g. "him-12345")\n'
    '  - "profile_url": the Himalayas profile URL\n'
    '  - "name": the candidate name, or null if missing\n'
    '  - "headline": the candidate headline/role, or null if missing\n'
    '  - "evidence": list of CandidateEvidence dicts with fields:\n'
    '      "field": field name (e.g. "name", "current_role", "skills", "github_url")\n'
    '      "value": the value\n'
    '      "source_url": the Himalayas profile URL\n'
    '      "source_type": "opt-in"\n'
    '      "verified": true\n'
    '      "inferred": false\n'
    '      "inference_basis": null\n\n'
    f"Write the JSON list of CandidateLead dicts to state['{StateKeys.LEADS_HIMALAYAS}'].\n"
    "If no candidates match, write an empty list. "
    "Never fabricate candidate data — only use what the tools return."
)


def make_himalayas_source_agent(model: str | None = None) -> LlmAgent:
    from google.adk.models.lite_llm import LiteLlm

    return LlmAgent(
        name="himalayas_source_agent",
        model=LiteLlm(model=model or OPENAI_MODEL, reasoning_effort="none"),
        instruction=_INSTRUCTION,
        tools=[McpToolset(connection_params=StreamableHTTPConnectionParams(url=_HIMALAYAS_MCP_URL))],
        output_key=StateKeys.LEADS_HIMALAYAS,
    )


himalayas_source_agent = make_himalayas_source_agent()