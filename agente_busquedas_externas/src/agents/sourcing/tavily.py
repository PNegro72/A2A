from google.adk.agents import LlmAgent
from google.adk.tools import FunctionTool

from src.agents.sourcing.mcp_client import call_mcp_tool
from src.agents.stage_guards import require_output
from src.config import OPENAI_MODEL, TAVILY_API_KEY
from src.domain.models import StateKeys, TavilyLeads

# mcp.tavily.com needs ~5s per round trip on its own.
_MCP_TIMEOUT_SECONDS = 30.0

# Web verification is the most expensive step per candidate; keep it bounded.
_MAX_CANDIDATES = 3


def _tavily_mcp_url() -> str:
    return f"https://mcp.tavily.com/mcp/?tavilyApiKey={TAVILY_API_KEY}"


# Only search is exposed: tavily_crawl / tavily_map / tavily_research are
# long-running agentic tools with no place in a per-candidate verification loop.
async def tavily_search(query: str, max_results: int = 5) -> dict:
    """Search the public web and return result URLs with snippets.

    Args:
        query: the search query, e.g. '"Jane Doe" FastAPI PostgreSQL github'.
        max_results: how many results to return (keep it small).
    """
    return await call_mcp_tool(
        _tavily_mcp_url(),
        "tavily_search",
        {"query": query, "max_results": max_results},
        timeout=_MCP_TIMEOUT_SECONDS,
    )

# NOTE: state values are injected by ADK through the `{key}` template syntax.
# This agent runs *after* the Himalayas agent (see orchestrator), so
# `{leads_himalayas}` is populated by the time this instruction is built. With
# the old prose ("read state['leads_himalayas']") the agent received nothing and
# answered "Please provide those state values".
_INSTRUCTION = (
    "You are a research and enrichment specialist. You corroborate candidate claims "
    "against their public web presence.\n\n"
    "HIRING REQUIREMENTS\n"
    "{hiring_requirements}\n\n"
    "LEADS ALREADY FOUND ON HIMALAYAS (JSON)\n"
    "{leads_himalayas}\n\n"
    "STEPS\n"
    f"1. Take up to {_MAX_CANDIDATES} of the leads above, preferring those whose "
    "headline matches the hiring requirements.\n"
    "2. For each one, call tavily_search once with max_results=5 and a query combining "
    "the candidate's name with the required skills or their github_url, to find "
    "corroborating public material (profiles, repositories, blog posts, talks).\n"
    "   Each result carries the 'url' and 'content' you must cite — one call at a time.\n"
    "3. Emit one lead per candidate for whom you found at least one real result.\n\n"
    "OUTPUT CONTRACT — enforced by a strict JSON schema; a response that does not match "
    "is rejected, so fill in every field.\n"
    'Return a JSON object with a single key "leads" holding a list of objects:\n'
    '  "source"      : always the string "tavily"\n'
    '  "raw_id"      : the raw_id of the Himalayas lead being enriched (pass through)\n'
    '  "profile_url" : the profile_url of that lead (pass through)\n'
    '  "name"        : the candidate name (pass through), or null\n'
    '  "headline"    : the candidate headline (pass through), or null\n'
    '  "github_url"  : the github_url of that lead when known, else null\n'
    '  "evidence"    : a list of evidence OBJECTS — never bare strings. One object per\n'
    "                  finding, each with:\n"
    '      "field"           : what the finding establishes, e.g. "confirmed_skill", '
    '"conference_talk", "open_source_contribution"\n'
    '      "value"           : the finding (string, number or boolean)\n'
    '      "source_url"      : REQUIRED — the exact URL of the Tavily result the finding\n'
    "                          came from. Never the candidate's profile URL unless Tavily\n"
    "                          actually returned it. Never empty, never invented.\n"
    '      "source_type"     : always "web-search"\n'
    '      "verified"        : false — web results are corroboration, not proof\n'
    '      "inferred"        : true when you read the conclusion out of the page rather\n'
    "                          than finding it stated\n"
    '      "inference_basis" : how you concluded it when inferred is true, else null\n\n'
    "RULES\n"
    "- Every lead MUST carry at least one evidence object with a URL Tavily returned.\n"
    "- Never fabricate URLs or findings, and never attach one candidate's URL to another.\n"
    "- A tool answering with a \"status\": \"unavailable\" payload means the search could not\n"
    "  run: skip that candidate instead of citing remembered or invented pages.\n"
    '- If you find nothing for anybody, return {"leads": []}.\n'
)


def make_tavily_research_agent(model: str | None = None) -> LlmAgent:
    from google.adk.models.lite_llm import LiteLlm

    return LlmAgent(
        name="tavily_research_agent",
        model=LiteLlm(model=model or OPENAI_MODEL, reasoning_effort="none"),
        instruction=_INSTRUCTION,
        tools=[FunctionTool(tavily_search)],
        output_schema=TavilyLeads,
        output_key=StateKeys.LEADS_TAVILY,
        after_agent_callback=require_output(
            "tavily_research_agent", StateKeys.LEADS_TAVILY
        ),
    )


tavily_research_agent = make_tavily_research_agent()
