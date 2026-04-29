import os

from google.adk.agents import LlmAgent
from google.adk.tools.mcp_tool.mcp_toolset import McpToolset, SseConnectionParams

from src.domain.models import StateKeys

_INSTRUCTION = (
    "You are a research and enrichment specialist.\n"
    f"Read state['{StateKeys.HIRING_REQUIREMENTS}'] for domain context.\n"
    f"Read state['{StateKeys.LEADS_HIMALAYAS}'] for existing candidate leads.\n"
    "For each candidate with a profile_url or github_url, use the Tavily search tool to:\n"
    "  - Verify claimed skills appear in their public presence\n"
    "  - Find any additional public information (blog posts, talks, open source work)\n"
    "Construct CandidateLead entries with evidence:\n"
    "  - source='tavily', source_type='web-search', verified=False, inferred=False\n"
    "  - Every evidence item MUST have a source_url from the Tavily result\n"
    f"Write the JSON list of CandidateLead dicts to state['{StateKeys.LEADS_TAVILY}'].\n"
    "If no enrichment is found, write an empty list. "
    "Never fabricate source URLs — only use URLs returned by Tavily."
)


def make_tavily_research_agent() -> LlmAgent:
    api_key = os.getenv("TAVILY_API_KEY", "")
    url = f"https://mcp.tavily.com/mcp/?tavilyApiKey={api_key}"
    return LlmAgent(
        name="tavily_research_agent",
        model="gemini-2.0-flash",
        instruction=_INSTRUCTION,
        tools=[McpToolset(connection_params=SseConnectionParams(url=url))],
        output_key=StateKeys.LEADS_TAVILY,
    )


# Module-level singleton for direct use and unit testing
tavily_research_agent = make_tavily_research_agent()
