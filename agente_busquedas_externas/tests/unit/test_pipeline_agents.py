"""
Tests for pipeline agent configuration and factory functions.
LLM reasoning is not unit-testable; we test output_key, name,
and that factory functions return correctly configured agents.
"""
from unittest.mock import AsyncMock

from google.adk.agents import LlmAgent

from src.domain.models import StateKeys


# ── JDAnalystAgent ────────────────────────────────────────────────────────

def test_jd_analyst_output_key():
    from src.agents.jd_analyst import jd_analyst_agent
    assert jd_analyst_agent.output_key == StateKeys.HIRING_REQUIREMENTS


def test_jd_analyst_name():
    from src.agents.jd_analyst import jd_analyst_agent
    assert jd_analyst_agent.name == "jd_analyst_agent"


# ── PlannerAgent ──────────────────────────────────────────────────────────

def test_planner_output_key():
    from src.agents.planner import planner_agent
    assert planner_agent.output_key == StateKeys.SEARCH_PLAN


def test_planner_name():
    from src.agents.planner import planner_agent
    assert planner_agent.name == "planner_agent"


# ── DeduplicatorAgent (factory) ───────────────────────────────────────────

def test_deduplicator_factory_returns_llm_agent():
    from src.agents.deduplicator import make_deduplicator_agent
    mock_repo = AsyncMock()
    agent = make_deduplicator_agent(mock_repo)
    assert isinstance(agent, LlmAgent)


def test_deduplicator_output_key():
    from src.agents.deduplicator import make_deduplicator_agent
    mock_repo = AsyncMock()
    agent = make_deduplicator_agent(mock_repo)
    assert agent.output_key == StateKeys.CANDIDATE_IDENTITIES


def test_deduplicator_name():
    from src.agents.deduplicator import make_deduplicator_agent
    mock_repo = AsyncMock()
    agent = make_deduplicator_agent(mock_repo)
    assert agent.name == "deduplicator_agent"


# ── ScorerAgent ───────────────────────────────────────────────────────────

def test_scorer_output_key():
    from src.agents.scorer import scorer_agent
    assert scorer_agent.output_key == StateKeys.CANDIDATE_SCORES


def test_scorer_name():
    from src.agents.scorer import scorer_agent
    assert scorer_agent.name == "scorer_agent"


# ── ReporterAgent (factory) ───────────────────────────────────────────────

def test_reporter_factory_returns_llm_agent():
    from src.agents.reporter import make_reporter_agent
    mock_pipeline_repo = AsyncMock()
    mock_report_repo = AsyncMock()
    agent = make_reporter_agent(mock_pipeline_repo, mock_report_repo)
    assert isinstance(agent, LlmAgent)


def test_reporter_output_key():
    from src.agents.reporter import make_reporter_agent
    agent = make_reporter_agent(AsyncMock(), AsyncMock())
    assert agent.output_key == StateKeys.SHORTLIST_REPORT


def test_reporter_name():
    from src.agents.reporter import make_reporter_agent
    agent = make_reporter_agent(AsyncMock(), AsyncMock())
    assert agent.name == "reporter_agent"
