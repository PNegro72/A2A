import os

from google.adk.agents import LlmAgent
from google.adk.tools.mcp_tool.mcp_toolset import McpToolset
from google.adk.tools.mcp_tool.mcp_session_manager import StreamableHTTPConnectionParams

from src.config import OPENAI_MODEL, TAVILY_API_KEY
from src.domain.models import StateKeys

_INSTRUCTION = (
    "You are a research and enrichment specialist.\n"
    f"Read state['{StateKeys.HIRING_REQUIREMENTS}'] for domain context.\n"
    f"Read state['{StateKeys.LEADS_HIMALAYAS}'] for existing candidate leads.\n"
    "For each candidate with a profile_url or github_url, use the Tavily search tool to:\n"
    "  - Verify claimed skills appear in their public presence\n"
    "  - Find any additional public information (blog posts, talks, open source work)\n\n"
    "Build a CandidateLead dict for each candidate with EXACTLY these fields:\n"
    '  - "source": "tavily"\n'
    '  - "raw_id": the same raw_id from the original Himalaya lead (pass through)\n'
    '  - "profile_url": the same profile_url from the original Himalaya lead (pass through)\n'
    '  - "name": the candidate name (pass through from original lead), or null\n'
    '  - "headline": the candidate headline (pass through), or null\n'
    '  - "evidence": list of CandidateEvidence dicts with fields:\n'
    '      "field": field name describing what was verified/found\n'
    '      "value": the finding\n'
    '      "source_url": MUST be a real URL from a Tavily result (never fabricate)\n'
    '      "source_type": "web-search"\n'
    '      "verified": false\n'
    '      "inferred": false\n'
    '      "inference_basis": null\n\n'
    f"Write the JSON list of CandidateLead dicts to state['{StateKeys.LEADS_TAVILY}'].\n"
    "If no enrichment is found, write an empty list. "
    "Never fabricate source URLs — only use URLs returned by Tavily."
)


def make_tavily_research_agent(model: str | None = None) -> LlmAgent:
    from google.adk.models.lite_llm import LiteLlm

    url = f"https://mcp.tavily.com/mcp/?tavilyApiKey={TAVILY_API_KEY}"
    return LlmAgent(
        name="tavily_research_agent",
        model=LiteLlm(model=model or OPENAI_MODEL),
        instruction=_INSTRUCTION,
        tools=[McpToolset(connection_params=StreamableHTTPConnectionParams(url=url))],
        output_key=StateKeys.LEADS_TAVILY,
    )


tavily_research_agent = make_tavily_research_agent()