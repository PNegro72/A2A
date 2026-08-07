import os

import httpx
from google.adk.agents import LlmAgent
from google.adk.tools import FunctionTool

from src.config import OPENAI_MODEL
from src.domain.models import StateKeys

_GITHUB_API = "https://api.github.com"


async def fetch_github_profile(client: httpx.AsyncClient, username: str) -> dict:
    token = os.getenv("GITHUB_TOKEN")
    r = await client.get(
        f"{_GITHUB_API}/users/{username}",
        headers={"Authorization": f"Bearer {token}"},
    )
    r.raise_for_status()
    return r.json()


async def fetch_github_repos(client: httpx.AsyncClient, username: str) -> list[dict]:
    token = os.getenv("GITHUB_TOKEN")
    r = await client.get(
        f"{_GITHUB_API}/users/{username}/repos",
        headers={"Authorization": f"Bearer {token}"},
        params={"sort": "updated", "per_page": 10},
    )
    r.raise_for_status()
    return r.json()


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


_INSTRUCTION = (
    "You are a technical profile researcher.\n"
    f"Read state['{StateKeys.LEADS_HIMALAYAS}'] to find candidates with GitHub URLs.\n"
    "For each candidate with a github_url, call get_github_profile then get_github_repos.\n\n"
    "Build a CandidateLead dict for each candidate with EXACTLY these fields:\n"
    '  - "source": "github"\n'
    '  - "raw_id": the GitHub login/username (from API field "login")\n'
    '  - "profile_url": the GitHub profile URL (from API field "html_url")\n'
    '  - "name": the display name (from API field "name"), or null if missing\n'
    '  - "headline": the bio (from API field "bio"), or null if missing\n'
    '  - "evidence": list of CandidateEvidence dicts with fields:\n'
    '      "field": field name (e.g. "name", "bio", "public_repos", "followers", "top_repo")\n'
    '      "value": the value\n'
    '      "source_url": "https://api.github.com/users/LOGIN" (replace LOGIN with the actual login)\n'
    '      "source_type": "public-api"\n'
    '      "verified": true\n'
    '      "inferred": false\n'
    '      "inference_basis": null\n\n'
    "Example output for user 'octocat':\n"
    '  {"source": "github", "raw_id": "octocat", "profile_url": "https://github.com/octocat", '
    '"name": "The Octocat", "headline": "GitHub mascot", "evidence": [...]}\n\n'
    f"Write the JSON list of CandidateLead dicts to state['{StateKeys.LEADS_GITHUB}'].\n"
    "If a candidate has no GitHub URL, skip them. "
    f"If GitHub is unreachable, write an empty list to state['{StateKeys.LEADS_GITHUB}'] "
    f"and append a RiskFlag(type='data-quality') to state['{StateKeys.RISK_FLAGS}']."
)


def make_github_source_agent(model: str | None = None) -> LlmAgent:
    from google.adk.models.lite_llm import LiteLlm

    return LlmAgent(
        name="github_source_agent",
        model=LiteLlm(model=model or OPENAI_MODEL, reasoning_effort="none"),
        instruction=_INSTRUCTION,
        tools=[FunctionTool(get_github_profile), FunctionTool(get_github_repos)],
        output_key=StateKeys.LEADS_GITHUB,
    )


github_source_agent = make_github_source_agent()