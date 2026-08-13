import uuid

from google.adk.agents import LlmAgent, ParallelAgent, SequentialAgent
from google.adk.models.lite_llm import LiteLlm
from google.adk.tools import FunctionTool, ToolContext

from src.agents.deduplicator import make_deduplicator_agent
from src.agents.jd_analyst import make_jd_analyst_agent
from src.agents.planner import make_planner_agent
from src.agents.reporter import make_reporter_agent
from src.agents.scorer import make_scorer_agent
from src.agents.sourcing.github import make_github_source_agent
from src.agents.sourcing.himalayas import make_himalayas_source_agent
from src.agents.sourcing.tavily import make_tavily_research_agent
from src.agents.stage_guards import require_output
from src.config import OPENAI_MODEL
from src.domain.models import StateKeys
from src.persistence.repositories import (
    CandidateRepository,
    PipelineRunRepository,
    ShortlistReportRepository,
)

_VALID_WORK_MODES = ("remote", "hybrid")


def create_orchestrator_agent(
    candidate_repo: CandidateRepository,
    pipeline_repo: PipelineRunRepository,
    report_repo: ShortlistReportRepository,
) -> SequentialAgent:
    """
    Factory: builds the full agente_busquedas_externas pipeline as a SequentialAgent.
    Closes over persistence repos for intake and factory sub-agents.
    """

    async def create_pipeline_run(
        job_description: str,
        location: str,
        work_mode: str,
        tool_context: ToolContext,
    ) -> dict:
        """Register the pipeline run and seed the shared state for later stages.

        An LlmAgent can only write its own `output_key`, so the intake stage has
        to seed job_description/location/work_mode/pipeline_run_id from inside a
        tool — that is what makes them available to the `{key}` placeholders in
        the downstream instructions.
        """
        if work_mode not in _VALID_WORK_MODES:
            return {
                "status": "error",
                "message": f"work_mode must be one of {_VALID_WORK_MODES}, got {work_mode!r}",
            }
        if not job_description.strip():
            return {"status": "error", "message": "job_description must not be empty"}

        run_id = str(uuid.uuid4())
        await pipeline_repo.create(run_id, job_description, location, work_mode)

        tool_context.state[StateKeys.JOB_DESCRIPTION] = job_description
        tool_context.state[StateKeys.LOCATION] = location or "anywhere"
        tool_context.state[StateKeys.WORK_MODE] = work_mode
        tool_context.state[StateKeys.PIPELINE_RUN_ID] = run_id
        tool_context.state.setdefault(StateKeys.RISK_FLAGS, [])
        return {"status": "created", "run_id": run_id}

    _model = LiteLlm(model=OPENAI_MODEL, reasoning_effort="none")

    intake_agent = LlmAgent(
        name="intake_agent",
        model=_model,
        instruction=(
            "You are the intake processor for the agente_busquedas_externas pipeline.\n\n"
            "REQUEST ALREADY PARSED BY THE SERVER (empty when the agent is driven "
            "directly)\n"
            "  job_description: {job_description?}\n"
            "  location: {location?}\n"
            "  work_mode: {work_mode?}\n\n"
            "If those are empty, read the same three fields from the incoming JSON "
            "message instead.\n\n"
            "Validate that job_description is non-empty and that work_mode is exactly "
            f"one of {_VALID_WORK_MODES}. If validation fails, reply with the error and "
            "STOP.\n"
            "Otherwise call create_pipeline_run(job_description, location, work_mode) "
            "exactly once — it registers the run and seeds the pipeline state — then "
            "reply with the returned run_id."
        ),
        tools=[FunctionTool(create_pipeline_run)],
        output_key="intake_complete",
        after_agent_callback=require_output("intake_agent", StateKeys.PIPELINE_RUN_ID),
    )

    # Himalayas is the only source that discovers candidates on its own; GitHub and
    # Tavily enrich what it found. Running all three in parallel (the previous
    # topology) meant GitHub and Tavily read `leads_himalayas` before their sibling
    # had written it — GitHub returned "[]" and Tavily asked for the state values.
    sourcing_phase = SequentialAgent(
        name="sourcing_phase",
        sub_agents=[
            make_himalayas_source_agent(model=OPENAI_MODEL),
            ParallelAgent(
                name="enrichment_phase",
                sub_agents=[
                    make_github_source_agent(model=OPENAI_MODEL),
                    make_tavily_research_agent(model=OPENAI_MODEL),
                ],
            ),
        ],
    )

    return SequentialAgent(
        name="agente_busquedas_externas_orchestrator",
        sub_agents=[
            intake_agent,
            make_jd_analyst_agent(model=OPENAI_MODEL),
            make_planner_agent(model=OPENAI_MODEL),
            sourcing_phase,
            make_deduplicator_agent(candidate_repo, model=OPENAI_MODEL),
            make_scorer_agent(model=OPENAI_MODEL),
            make_reporter_agent(pipeline_repo, report_repo, model=OPENAI_MODEL),
        ],
    )
