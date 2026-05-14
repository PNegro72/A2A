from google.adk.agents import LlmAgent
from google.adk.tools import FunctionTool

from src.config import OPENAI_MODEL
from src.domain.models import ShortlistReport, StateKeys
from src.persistence.repositories import PipelineRunRepository, ShortlistReportRepository


def make_reporter_agent(
    pipeline_repo: PipelineRunRepository,
    report_repo: ShortlistReportRepository,
    model: str | None = None,
) -> LlmAgent:
    from google.adk.models.lite_llm import LiteLlm

    async def persist_report(run_id: str, report_json: str) -> str:
        """Persist the final ShortlistReport and mark the pipeline run as complete."""
        import json
        import logging

        logger = logging.getLogger("google_adk." + __name__)

        # Pre-process: fix common LLM schema mistakes before validation
        try:
            raw = json.loads(report_json)
        except json.JSONDecodeError as e:
            logger.warning(
                "persist_report: invalid JSON for run %s: %s. Data: %.300s",
                run_id, e, report_json,
            )
            return f"skipped:{run_id}"
        for c in raw.get("candidates", []):
            fixed_flags = []
            for flag in c.get("risk_flags", []):
                if isinstance(flag, str):
                    # LLM output a bare string instead of a RiskFlag dict
                    fixed_flags.append(
                        {"type": "data-quality", "description": flag, "severity": "low"}
                    )
                elif isinstance(flag, dict):
                    fixed_flags.append(flag)
                else:
                    logger.warning("persist_report: skipping non-dict risk_flag: %s", flag)
            c["risk_flags"] = fixed_flags
        report = ShortlistReport.model_validate(raw)
        await report_repo.save(run_id, report)
        await pipeline_repo.complete(run_id)
        return f"persisted:{run_id}"

    return LlmAgent(
        name="reporter_agent",
        model=LiteLlm(model=model or OPENAI_MODEL),
        instruction=(
            "You are a reporting specialist.\n"
            f"Read state['{StateKeys.CANDIDATE_SCORES}'] and "
            f"state['{StateKeys.HIRING_REQUIREMENTS}'].\n\n"
            "Build a ShortlistReport JSON dict with EXACTLY these fields:\n"
            '  "job_title": str — derived from hiring_requirements, or the original role title\n'
            '  "generated_at": ISO 8601 datetime string (will be overridden on persist)\n'
            '  "candidates": list of CandidateScore dicts (taken from CANDIDATE_SCORES, '
            "sorted by score descending)\n"
            '  "sources_used": list of source names actually queried, e.g. ["github"]\n'
            '  "caveats": list of str — MUST be non-empty. Include data provenance and '
            "any RiskFlags of severity >= medium from the scores\n\n"
            "RULES:\n"
            "- Every candidate MUST have >= 1 evidence item in their merged_leads\n"
            "- If candidates list is empty, add caveat: "
            "'No candidates found from configured sources'\n"
            f"- Call persist_report(state['{StateKeys.PIPELINE_RUN_ID}'], report_json) "
            "  to save and complete the run\n"
            f"- Write the ShortlistReport JSON dict to state['{StateKeys.SHORTLIST_REPORT}']"
        ),
        tools=[FunctionTool(persist_report)],
        output_key=StateKeys.SHORTLIST_REPORT,
    )