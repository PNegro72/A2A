"""
Tests for source agent pure functions and agent configuration.
ADK LlmAgents are LLM-driven — we test the tool functions (pure async HTTP)
and agent configuration (output_key, name).
"""
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.domain.models import StateKeys


# ── GitHub tool functions ─────────────────────────────────────────────────

async def test_fetch_github_profile_returns_login_and_name():
    from src.agents.sourcing.github import fetch_github_profile

    mock_client = AsyncMock()
    mock_response = MagicMock()
    mock_response.json.return_value = {
        "login": "testuser",
        "name": "Test User",
        "bio": "Python dev",
        "public_repos": 42,
        "html_url": "https://github.com/testuser",
    }
    mock_response.raise_for_status = MagicMock()
    mock_client.get.return_value = mock_response

    result = await fetch_github_profile(mock_client, "testuser")

    assert result["login"] == "testuser"
    assert result["public_repos"] == 42
    # GITHUB_TOKEN unset -> no Authorization header at all. Sending an empty
    # "Bearer" makes GitHub answer 401; omitting the header gets a 200 under the
    # unauthenticated rate limit.
    mock_client.get.assert_called_once_with(
        "https://api.github.com/users/testuser",
        headers={},
    )


async def test_fetch_github_profile_uses_token_from_env():
    from src.agents.sourcing.github import fetch_github_profile

    mock_client = AsyncMock()
    mock_response = MagicMock()
    mock_response.json.return_value = {"login": "alice", "public_repos": 10, "html_url": "x"}
    mock_response.raise_for_status = MagicMock()
    mock_client.get.return_value = mock_response

    with patch.dict("os.environ", {"GITHUB_TOKEN": "ghp_secret"}):
        await fetch_github_profile(mock_client, "alice")

    call_kwargs = mock_client.get.call_args
    assert "ghp_secret" in call_kwargs[1]["headers"]["Authorization"]


async def test_fetch_github_repos_returns_list_of_repos():
    from src.agents.sourcing.github import fetch_github_repos

    mock_client = AsyncMock()
    mock_response = MagicMock()
    mock_response.json.return_value = [
        {"name": "repo-a", "language": "Python", "stargazers_count": 10},
        {"name": "repo-b", "language": "Go", "stargazers_count": 3},
    ]
    mock_response.raise_for_status = MagicMock()
    mock_client.get.return_value = mock_response

    result = await fetch_github_repos(mock_client, "testuser")

    assert len(result) == 2
    assert result[0]["name"] == "repo-a"
    assert result[1]["language"] == "Go"


async def test_fetch_github_repos_empty_when_no_repos():
    from src.agents.sourcing.github import fetch_github_repos

    mock_client = AsyncMock()
    mock_response = MagicMock()
    mock_response.json.return_value = []
    mock_response.raise_for_status = MagicMock()
    mock_client.get.return_value = mock_response

    result = await fetch_github_repos(mock_client, "newuser")

    assert result == []
    mock_client.get.assert_called_once()


# ── Agent configuration ───────────────────────────────────────────────────

def test_himalayas_agent_output_key():
    from src.agents.sourcing.himalayas import himalayas_source_agent
    assert himalayas_source_agent.output_key == StateKeys.LEADS_HIMALAYAS


def test_himalayas_agent_name():
    from src.agents.sourcing.himalayas import himalayas_source_agent
    assert himalayas_source_agent.name == "himalayas_source_agent"


def test_tavily_agent_output_key():
    from src.agents.sourcing.tavily import tavily_research_agent
    assert tavily_research_agent.output_key == StateKeys.LEADS_TAVILY


def test_github_agent_output_key():
    from src.agents.sourcing.github import github_source_agent
    assert github_source_agent.output_key == StateKeys.LEADS_GITHUB


# ── Evidence contract is enforced structurally, not by prompt alone ────────

def test_source_agents_declare_output_schema():
    from src.domain.models import GithubLeads, HimalayasLeads, TavilyLeads
    from src.agents.sourcing.github import github_source_agent
    from src.agents.sourcing.himalayas import himalayas_source_agent
    from src.agents.sourcing.tavily import tavily_research_agent

    assert himalayas_source_agent.output_schema is HimalayasLeads
    assert github_source_agent.output_schema is GithubLeads
    assert tavily_research_agent.output_schema is TavilyLeads


def test_source_agent_instructions_use_adk_state_placeholders():
    """State reaches an agent through `{key}` injection; prose does not."""
    from src.agents.sourcing.github import github_source_agent
    from src.agents.sourcing.tavily import tavily_research_agent

    for agent in (github_source_agent, tavily_research_agent):
        assert "{leads_himalayas}" in agent.instruction
        assert "state['leads_himalayas']" not in agent.instruction
