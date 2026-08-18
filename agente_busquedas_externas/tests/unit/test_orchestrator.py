"""
Tests for orchestrator factory and A2A wiring.
"""
from unittest.mock import AsyncMock

from google.adk.agents import LlmAgent, ParallelAgent, SequentialAgent


def test_create_orchestrator_returns_sequential_agent():
    from src.agents.orchestrator import create_orchestrator_agent
    agent = create_orchestrator_agent(AsyncMock(), AsyncMock(), AsyncMock())
    assert isinstance(agent, SequentialAgent)


def test_orchestrator_name():
    from src.agents.orchestrator import create_orchestrator_agent
    agent = create_orchestrator_agent(AsyncMock(), AsyncMock(), AsyncMock())
    assert agent.name == "agente_busquedas_externas_orchestrator"


def test_orchestrator_has_seven_sub_agents():
    from src.agents.orchestrator import create_orchestrator_agent
    agent = create_orchestrator_agent(AsyncMock(), AsyncMock(), AsyncMock())
    # intake, jd_analyst, planner, sourcing_phase, deduplicator, scorer, reporter
    assert len(agent.sub_agents) == 7


def test_orchestrator_first_sub_agent_is_intake():
    from src.agents.orchestrator import create_orchestrator_agent
    agent = create_orchestrator_agent(AsyncMock(), AsyncMock(), AsyncMock())
    assert agent.sub_agents[0].name == "intake_agent"


def test_orchestrator_sourcing_phase_runs_himalayas_before_enrichment():
    """GitHub and Tavily consume state['leads_himalayas'], so Himalayas cannot be
    their parallel sibling — it has to complete first."""
    from src.agents.orchestrator import create_orchestrator_agent
    agent = create_orchestrator_agent(AsyncMock(), AsyncMock(), AsyncMock())
    sourcing_phase = agent.sub_agents[3]
    assert isinstance(sourcing_phase, SequentialAgent)
    assert sourcing_phase.name == "sourcing_phase"
    assert sourcing_phase.sub_agents[0].name == "himalayas_source_agent"
    assert isinstance(sourcing_phase.sub_agents[1], ParallelAgent)


def test_enrichment_phase_runs_github_and_tavily_in_parallel():
    from src.agents.orchestrator import create_orchestrator_agent
    agent = create_orchestrator_agent(AsyncMock(), AsyncMock(), AsyncMock())
    enrichment_phase = agent.sub_agents[3].sub_agents[1]
    assert isinstance(enrichment_phase, ParallelAgent)
    assert {a.name for a in enrichment_phase.sub_agents} == {
        "github_source_agent",
        "tavily_research_agent",
    }


def test_sourcing_phase_has_three_source_agents():
    from src.agents.orchestrator import create_orchestrator_agent
    agent = create_orchestrator_agent(AsyncMock(), AsyncMock(), AsyncMock())
    sourcing_phase = agent.sub_agents[3]
    names = set()
    for sub in sourcing_phase.sub_agents:
        names.update(
            {a.name for a in sub.sub_agents} if sub.sub_agents else {sub.name}
        )
    assert names == {
        "himalayas_source_agent",
        "github_source_agent",
        "tavily_research_agent",
    }


def test_orchestrator_last_sub_agent_is_reporter():
    from src.agents.orchestrator import create_orchestrator_agent
    agent = create_orchestrator_agent(AsyncMock(), AsyncMock(), AsyncMock())
    assert agent.sub_agents[-1].name == "reporter_agent"
