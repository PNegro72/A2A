import os

import httpx
from google.adk.agents import LlmAgent
from google.adk.tools import FunctionTool

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
    async with httpx.AsyncClient() as client:
        return await fetch_github_profile(client, username)


async def get_github_repos(username: str) -> list[dict]:
    """ADK tool: fetch a GitHub user's top repositories."""
    async with httpx.AsyncClient() as client:
        return await fetch_github_repos(client, username)


_INSTRUCTION = (
    "You are a technical profile researcher.\n"
    f"Read state['{StateKeys.LEADS_HIMALAYAS}'] to find candidates with GitHub URLs.\n"
    "For each candidate with a github_url, call get_github_profile then get_github_repos.\n"
    "Construct CandidateLead entries with technical evidence (source='github', "
    "source_type='public-api', verified=True, inferred=False for explicit fields; "
    "inferred=True with inference_basis for seniority derived from activity).\n"
    f"Write the JSON list of CandidateLead dicts to state['{StateKeys.LEADS_GITHUB}'].\n"
    "If a candidate has no GitHub URL, skip them. "
    f"If GitHub is unreachable, write an empty list to state['{StateKeys.LEADS_GITHUB}'] "
    f"and append a RiskFlag(type='data-quality') to state['{StateKeys.RISK_FLAGS}']."
)


def make_github_source_agent() -> LlmAgent:
    return LlmAgent(
        name="github_source_agent",
        model="gemini-2.0-flash",
        instruction=_INSTRUCTION,
        tools=[FunctionTool(get_github_profile), FunctionTool(get_github_repos)],
        output_key=StateKeys.LEADS_GITHUB,
    )


# Module-level singleton for direct use and unit testing
github_source_agent = make_github_source_agent()
