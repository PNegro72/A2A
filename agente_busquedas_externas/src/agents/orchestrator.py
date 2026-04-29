import uuid

from google.adk.agents import LlmAgent, ParallelAgent, SequentialAgent
from google.adk.tools import FunctionTool

from src.agents.deduplicator import make_deduplicator_agent
from src.agents.jd_analyst import make_jd_analyst_agent
from src.agents.planner import make_planner_agent
from src.agents.reporter import make_reporter_agent
from src.agents.scorer import make_scorer_agent
from src.agents.sourcing.github import make_github_source_agent
from src.agents.sourcing.himalayas import make_himalayas_source_agent
from src.agents.sourcing.tavily import make_tavily_research_agent
from src.domain.models import StateKeys
from src.persistence.repositories import (
    CandidateRepository,
    PipelineRunRepository,
    ShortlistReportRepository,
)


def create_orchestrator_agent(
    candidate_repo: CandidateRepository,
    pipeline_repo: PipelineRunRepository,
    report_repo: ShortlistReportRepository,
) -> SequentialAgent:
    """
    Factory: builds the full agente_busquedas_externas pipeline as a SequentialAgent.
    Closes over persistence repos for intake and factory sub-agents.
    """

    async def create_pipeline_run(job_description: str, location: str, work_mode: str) -> str:
        """Create a pipeline run record and return the run_id."""
        run_id = str(uuid.uuid4())
        await pipeline_repo.create(run_id, job_description, location, work_mode)
        return run_id

    intake_agent = LlmAgent(
        name="intake_agent",
        model="gemini-2.0-flash",
        instruction=(
            "You are the intake processor for the agente_busquedas_externas pipeline.\n"
            "The incoming message is a JSON object with three required fields:\n"
            "  job_description: str  — the full job description text\n"
            "  location: str         — city, country, or 'anywhere'\n"
            "  work_mode: str        — exactly 'remote' or 'hybrid'\n\n"
            "Validation:\n"
            "- If any field is missing, return an error message and STOP.\n"
            "- If work_mode is not 'remote' or 'hybrid', return an error and STOP.\n\n"
            "On success:\n"
            "1. Call create_pipeline_run(job_description, location, work_mode) "
            "   and store the returned run_id.\n"
            f"2. Write job_description to state['{StateKeys.JOB_DESCRIPTION}']\n"
            f"3. Write location to state['{StateKeys.LOCATION}']\n"
            f"4. Write work_mode to state['{StateKeys.WORK_MODE}']\n"
            f"5. Write run_id to state['{StateKeys.PIPELINE_RUN_ID}']\n"
            f"6. Initialize state['{StateKeys.RISK_FLAGS}'] = []\n"
        ),
        tools=[FunctionTool(create_pipeline_run)],
        output_key="intake_complete",
    )

    sourcing_phase = ParallelAgent(
        name="sourcing_phase",
        sub_agents=[
            make_himalayas_source_agent(),
            make_github_source_agent(),
            make_tavily_research_agent(),
        ],
    )

    return SequentialAgent(
        name="agente_busquedas_externas_orchestrator",
        sub_agents=[
            intake_agent,
            make_jd_analyst_agent(),
            make_planner_agent(),
            sourcing_phase,
            make_deduplicator_agent(candidate_repo),
            make_scorer_agent(),
            make_reporter_agent(pipeline_repo, report_repo),
        ],
    )
