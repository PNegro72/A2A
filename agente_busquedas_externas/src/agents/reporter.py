from google.adk.agents import LlmAgent
from google.adk.tools import FunctionTool

from src.domain.models import ShortlistReport, StateKeys
from src.persistence.repositories import PipelineRunRepository, ShortlistReportRepository


def make_reporter_agent(
    pipeline_repo: PipelineRunRepository,
    report_repo: ShortlistReportRepository,
) -> LlmAgent:
    """Factory: returns a ReporterAgent closed over persistence repositories."""

    async def persist_report(run_id: str, report_json: str) -> str:
        """Persist the final ShortlistReport and mark the pipeline run as complete."""
        import json
        report = ShortlistReport.model_validate_json(report_json)
        await report_repo.save(run_id, report)
        await pipeline_repo.complete(run_id)
        return f"persisted:{run_id}"

    return LlmAgent(
        name="reporter_agent",
        model="gemini-2.0-flash",
        instruction=(
            "You are a reporting specialist.\n"
            f"Read state['{StateKeys.CANDIDATE_SCORES}'] and "
            f"state['{StateKeys.HIRING_REQUIREMENTS}'].\n\n"
            "Build a ShortlistReport JSON object:\n"
            "  job_title: derived from hiring_requirements.domain\n"
            "  candidates: CandidateScore list ordered by score descending\n"
            "  sources_used: list of source names actually queried\n"
            "  caveats: list of important notes (MUST be non-empty — include at least "
            "    data provenance and any RiskFlags of severity >= medium)\n\n"
            "RULES:\n"
            "- Every candidate MUST have >= 1 evidence item in their merged_leads\n"
            "- If candidates list is empty, add caveat: "
            "  'No candidates found from configured sources'\n"
            f"- Call persist_report(state['{StateKeys.PIPELINE_RUN_ID}'], report_json) "
            "  to save and complete the run\n"
            f"- Write the ShortlistReport JSON to state['{StateKeys.SHORTLIST_REPORT}']"
        ),
        tools=[FunctionTool(persist_report)],
        output_key=StateKeys.SHORTLIST_REPORT,
    )
