from google.adk.agents import LlmAgent
from google.adk.tools import FunctionTool

from src.agents.sourcing.mcp_client import call_mcp_tool
from src.agents.stage_guards import require_output
from src.config import OPENAI_MODEL
from src.domain.models import HimalayasLeads, StateKeys

_HIMALAYAS_MCP_URL = "https://mcp.himalayas.app/mcp"

# The remote server needs ~3-5s per round trip; 30s leaves room for a slow
# search without letting a hung call stall the pipeline.
_MCP_TIMEOUT_SECONDS = 30.0

# Cap the fan-out: every downstream stage re-emits these leads, so an unbounded
# search makes the later prompts (and their structured outputs) blow up.
_MAX_CANDIDATES = 5


# The Himalayas MCP exposes ~45 tools, most of them write operations on the
# caller's own account (post_job_public, start_conversation, update_profile...).
# Wrapping the two read tools we need keeps those out of the agent's reach and
# keeps the parameter list honest — search_talent takes no skills/remote/limit,
# and a hallucinated parameter used to be silently dropped by the server.
async def search_talent(keyword: str, country: str = "", sort: str = "relevant") -> dict:
    """Search opt-in candidate profiles on the Himalayas remote-talent board.

    Args:
        keyword: free-text query, e.g. 'python backend developer'.
        country: optional country filter, e.g. 'Germany'. Empty means worldwide.
        sort: 'relevant' or 'recent'.
    """
    args: dict[str, object] = {"keyword": keyword, "sort": sort}
    if country:
        args["country"] = country
    return await call_mcp_tool(
        _HIMALAYAS_MCP_URL, "search_talent", args, timeout=_MCP_TIMEOUT_SECONDS
    )


async def get_talent_profile(talent_slug: str) -> dict:
    """Read one Himalayas talent profile in full.

    Args:
        talent_slug: the slug from the profile URL https://himalayas.app/@SLUG.
    """
    return await call_mcp_tool(
        _HIMALAYAS_MCP_URL,
        "get_talent_profile",
        {"talent_slug": talent_slug},
        timeout=_MCP_TIMEOUT_SECONDS,
    )

# NOTE: state values are injected by ADK through the `{key}` template syntax.
# Referring to state in prose ("read state['x']") does nothing — the agent then
# only sees whatever leaked through the conversation history, which is empty for
# a sibling under a ParallelAgent.
_INSTRUCTION = (
    "You are a talent sourcing specialist working the Himalayas remote-talent board.\n\n"
    "HIRING REQUIREMENTS\n"
    "{hiring_requirements}\n\n"
    "SEARCH PLAN\n"
    "{search_plan}\n\n"
    "STEPS\n"
    "1. Call search_talent ONCE:\n"
    "     keyword : short free-text query, e.g. 'python backend developer' — build it "
    "from the role and the primary required skills\n"
    "     country : only when the work mode is hybrid and the location constrains the "
    "search; leave it empty for remote roles\n"
    "     sort    : 'relevant'\n"
    "2. The result text is markdown. Every candidate carries a profile link of the form\n"
    "   https://himalayas.app/@SLUG (sometimes with a tracking query string). The talent\n"
    "   slug is the part after '@', without any '?...' suffix.\n"
    f"3. Choose at most {_MAX_CANDIDATES} candidates whose role and headline best match "
    "the hiring requirements and call get_talent_profile(talent_slug=SLUG) for each, one "
    "call at a time.\n"
    "4. Emit one lead per profile you actually retrieved.\n\n"
    "OUTPUT CONTRACT — enforced by a strict JSON schema; a response that does not match "
    "is rejected, so fill in every field.\n"
    'Return a JSON object with a single key "leads" holding a list of objects:\n'
    '  "source"      : always the string "himalayas"\n'
    '  "raw_id"      : the talent slug\n'
    '  "profile_url" : https://himalayas.app/@SLUG (no tracking query string)\n'
    '  "name"        : candidate name, or null when the profile has none\n'
    '  "headline"    : current role / headline, or null\n'
    '  "github_url"  : the GitHub profile URL from the profile\'s Links/Tech Stack '
    "section when it has one, else null\n"
    '  "evidence"    : a list of evidence OBJECTS — never bare strings. One object per\n'
    "                  observable fact, each with:\n"
    '      "field"           : what the fact is about, e.g. "current_role", "skills", '
    '"years_experience"\n'
    '      "value"           : the observed value (string, number or boolean)\n'
    '      "source_url"      : REQUIRED — the exact URL you read this fact from, normally\n'
    "                          the profile URL. Never empty, never invented.\n"
    '      "source_type"     : always "opt-in" (Himalayas profiles are opt-in)\n'
    '      "verified"        : true when read directly off the profile\n'
    '      "inferred"        : true only when you derived the value instead of reading it\n'
    '      "inference_basis" : how you derived it when inferred is true, else null\n\n'
    "RULES\n"
    "- Every lead MUST carry at least one evidence object.\n"
    "- Never fabricate candidates, URLs or facts — only report what the tools returned.\n"
    "- Keyword search on a remote-talent board returns loosely related people. Report the\n"
    "  closest profiles you retrieved even when the match is weak — scoring and filtering\n"
    "  happen downstream — but never pad the list with candidates you did not fetch.\n"
    "- A tool answering with a \"status\": \"unavailable\" payload means the board could not\n"
    "  be reached: skip that candidate, never substitute remembered or invented data.\n"
    '- If the search itself returns nothing, return {"leads": []}.\n'
)


def make_himalayas_source_agent(model: str | None = None) -> LlmAgent:
    from google.adk.models.lite_llm import LiteLlm

    return LlmAgent(
        name="himalayas_source_agent",
        model=LiteLlm(model=model or OPENAI_MODEL, reasoning_effort="none"),
        instruction=_INSTRUCTION,
        tools=[FunctionTool(search_talent), FunctionTool(get_talent_profile)],
        output_schema=HimalayasLeads,
        output_key=StateKeys.LEADS_HIMALAYAS,
        after_agent_callback=require_output(
            "himalayas_source_agent", StateKeys.LEADS_HIMALAYAS
        ),
    )


himalayas_source_agent = make_himalayas_source_agent()
