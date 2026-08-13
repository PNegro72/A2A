import os

import httpx
from google.adk.agents import LlmAgent
from google.adk.tools import FunctionTool

from src.agents.stage_guards import require_output
from src.config import OPENAI_MODEL
from src.domain.models import GithubLeads, StateKeys

_GITHUB_API = "https://api.github.com"

# Unauthenticated GitHub allows 60 core requests/hour, and every enrichment
# costs two (profile + repos). Cap the fan-out so one run cannot exhaust the
# budget for the next.
_MAX_ENRICHMENTS = 5


def _auth_headers() -> dict[str, str]:
    """Build the GitHub auth header, omitting it when no token is configured.

    Sending an empty ``Authorization: Bearer`` makes GitHub reply 401 "Bad
    credentials", whereas sending no header falls back to the unauthenticated
    rate limit (60 req/h) and still returns public profile data.
    """
    token = os.getenv("GITHUB_TOKEN")
    return {"Authorization": f"Bearer {token}"} if token else {}


async def fetch_github_profile(client: httpx.AsyncClient, username: str) -> dict:
    r = await client.get(
        f"{_GITHUB_API}/users/{username}",
        headers=_auth_headers(),
    )
    r.raise_for_status()
    return r.json()


async def fetch_github_repos(client: httpx.AsyncClient, username: str) -> list[dict]:
    r = await client.get(
        f"{_GITHUB_API}/users/{username}/repos",
        headers=_auth_headers(),
        params={"sort": "updated", "per_page": 10},
    )
    r.raise_for_status()
    return r.json()


async def fetch_github_user_search(
    client: httpx.AsyncClient, query: str, per_page: int = _MAX_ENRICHMENTS
) -> list[dict]:
    r = await client.get(
        f"{_GITHUB_API}/search/users",
        headers=_auth_headers(),
        params={"q": query, "per_page": per_page},
    )
    r.raise_for_status()
    items = r.json().get("items", [])
    # Trim to the fields a lead needs; the raw payload is mostly API plumbing.
    return [
        {"login": i.get("login"), "html_url": i.get("html_url")}
        for i in items
        if i.get("login")
    ]


async def get_github_profile(username: str) -> dict:
    """ADK tool: fetch a GitHub user's public profile."""
    try:
        async with httpx.AsyncClient() as client:
            return await fetch_github_profile(client, username)
    except Exception as e:
        return {"error": str(e), "status": "unavailable"}


async def get_github_repos(username: str) -> list[dict]:
    """ADK tool: fetch a GitHub user's top repositories."""
    try:
        async with httpx.AsyncClient() as client:
            return await fetch_github_repos(client, username)
    except Exception as e:
        return [{"error": str(e), "status": "unavailable"}]


async def search_github_users(query: str) -> list[dict]:
    """ADK tool: search public GitHub users (e.g. 'language:python location:remote')."""
    try:
        async with httpx.AsyncClient() as client:
            return await fetch_github_user_search(client, query)
    except Exception as e:
        return [{"error": str(e), "status": "unavailable"}]


# NOTE: state values are injected by ADK through the `{key}` template syntax.
# This agent runs *after* the Himalayas agent (see orchestrator), so
# `{leads_himalayas}` is populated by the time this instruction is built.
_INSTRUCTION = (
    "You are a technical profile researcher. You turn public GitHub activity into "
    "verifiable technical signal.\n\n"
    "HIRING REQUIREMENTS\n"
    "{hiring_requirements}\n\n"
    "SEARCH PLAN\n"
    "{search_plan}\n\n"
    "LEADS ALREADY FOUND ON HIMALAYAS (JSON)\n"
    "{leads_himalayas}\n\n"
    "STEPS\n"
    "1. Take every lead above whose github_url is not null and extract its username\n"
    "   (the last path segment of the URL).\n"
    "2. Then call search_github_users exactly once — always, even when step 1 already\n"
    "   found usernames — with a query built from the 'github' entry of the search plan\n"
    "   (for example 'language:python location:remote'). GitHub is a source in its own\n"
    "   right, not only an enricher.\n"
    f"3. Take at most {_MAX_ENRICHMENTS} usernames in total, the ones from step 1 first, "
    "and for each call get_github_profile and then get_github_repos.\n"
    "4. Emit one lead per username whose profile call succeeded.\n\n"
    "OUTPUT CONTRACT — enforced by a strict JSON schema; a response that does not match "
    "is rejected, so fill in every field.\n"
    'Return a JSON object with a single key "leads" holding a list of objects:\n'
    '  "source"      : always the string "github"\n'
    '  "raw_id"      : the GitHub login (API field "login")\n'
    '  "profile_url" : the GitHub profile URL (API field "html_url")\n'
    '  "name"        : API field "name", or null\n'
    '  "headline"    : API field "bio", or null\n'
    '  "github_url"  : the same GitHub profile URL\n'
    '  "evidence"    : a list of evidence OBJECTS — never bare strings. One object per\n'
    "                  observable fact, each with:\n"
    '      "field"           : e.g. "bio", "public_repos", "followers", "top_repo", '
    '"repo_language"\n'
    '      "value"           : the observed value (string, number or boolean)\n'
    '      "source_url"      : REQUIRED — the exact URL the fact came from:\n'
    "                          https://api.github.com/users/LOGIN for profile facts,\n"
    "                          the repository html_url for repository facts.\n"
    '      "source_type"     : always "public-api"\n'
    '      "verified"        : true for values read straight from the API\n'
    '      "inferred"        : true only when you derived the value instead of reading it\n'
    '      "inference_basis" : how you derived it when inferred is true, else null\n\n'
    "RULES\n"
    "- Every lead MUST carry at least one evidence object, and every evidence object MUST\n"
    "  carry the real URL it came from. Never reuse another candidate's URL.\n"
    "- Skip candidates whose profile call returned an error, and skip leads with no\n"
    "  GitHub presence — do not invent one.\n"
    '- If nothing could be retrieved, return {"leads": []}.\n'
)


def make_github_source_agent(model: str | None = None) -> LlmAgent:
    from google.adk.models.lite_llm import LiteLlm

    return LlmAgent(
        name="github_source_agent",
        model=LiteLlm(model=model or OPENAI_MODEL, reasoning_effort="none"),
        instruction=_INSTRUCTION,
        tools=[
            FunctionTool(get_github_profile),
            FunctionTool(get_github_repos),
            FunctionTool(search_github_users),
        ],
        output_schema=GithubLeads,
        output_key=StateKeys.LEADS_GITHUB,
        after_agent_callback=require_output(
            "github_source_agent", StateKeys.LEADS_GITHUB
        ),
    )


github_source_agent = make_github_source_agent()
