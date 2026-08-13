import json
import logging

from google.adk.agents import LlmAgent
from google.adk.agents.callback_context import CallbackContext
from pydantic import ValidationError

from src.agents.stage_guards import PipelineStageError, require_any_items, require_output
from src.config import OPENAI_MODEL
from src.domain.models import ShortlistReport, ShortlistReportOut, StateKeys
from src.persistence.repositories import PipelineRunRepository, ShortlistReportRepository

logger = logging.getLogger("google_adk." + __name__)

_INSTRUCTION = (
    "You are a reporting specialist.\n\n"
    "HIRING REQUIREMENTS\n"
    "{hiring_requirements}\n\n"
    "SCORED CANDIDATES (JSON)\n"
    "{candidate_scores}\n\n"
    "OUTPUT CONTRACT — enforced by a strict JSON schema; a response that does not match "
    "is rejected.\n"
    "Return a JSON object with these keys:\n"
    '  "job_title"    : the role title from the hiring requirements\n'
    '  "candidates"   : the scored candidates, sorted by score descending, each copied\n'
    "                   VERBATIM from the input — candidate_id, score, reasoning,\n"
    "                   risk_flags and the complete merged_leads with every evidence\n"
    "                   object and its source_url. The entrevistas agent builds the\n"
    "                   interview kit from merged_leads, so it must not be omitted.\n"
    '  "sources_used" : the sources that actually produced the evidence you are '
    'reporting, e.g. ["himalayas", "github", "tavily"]\n'
    '  "caveats"      : non-empty list of strings — data provenance plus every risk flag\n'
    "                   of severity medium or high\n\n"
    "RULES\n"
    "- Report every scored candidate; do not drop the weak ones, flag them in caveats.\n"
    "- Never add a candidate, a lead or an evidence item that is not in the input.\n"
    "- If the input holds no candidates, return an empty candidates list and the caveat\n"
    "  'No candidates found from configured sources'.\n"
)


def make_reporter_agent(
    pipeline_repo: PipelineRunRepository,
    report_repo: ShortlistReportRepository,
    model: str | None = None,
) -> LlmAgent:
    from google.adk.models.lite_llm import LiteLlm

    async def _persist_report(callback_context: CallbackContext) -> None:
        """Validate and persist the final report.

        Deterministic Python rather than a tool call: the report is the largest
        payload of the run, and handing it to the model as a JSON string argument
        is exactly where truncation used to lose candidates. The report the API
        returns is therefore the same object that was validated and stored.
        """
        raw = callback_context.state.get(StateKeys.SHORTLIST_REPORT)
        if isinstance(raw, str):
            raw = json.loads(raw)
        try:
            report = ShortlistReport.model_validate(raw)
        except ValidationError as exc:
            raise PipelineStageError(
                "reporter_agent produced a report that violates the domain "
                f"contract: {exc.errors(include_url=False)}"
            ) from exc

        run_id = callback_context.state.get(StateKeys.PIPELINE_RUN_ID)
        if not run_id:
            raise PipelineStageError(
                f"state['{StateKeys.PIPELINE_RUN_ID}'] is missing — the intake stage "
                "never registered this run, so the report cannot be persisted."
            )
        await report_repo.save(run_id, report)
        await pipeline_repo.complete(run_id)
        logger.info(
            "[reporter] run %s persisted: %d candidate(s), %d evidence item(s)",
            run_id,
            len(report.candidates),
            sum(
                len(lead.evidence)
                for candidate in report.candidates
                for lead in candidate.merged_leads
            ),
        )

    return LlmAgent(
        name="reporter_agent",
        model=LiteLlm(model=model or OPENAI_MODEL, reasoning_effort="none"),
        instruction=_INSTRUCTION,
        output_schema=ShortlistReportOut,
        output_key=StateKeys.SHORTLIST_REPORT,
        before_agent_callback=require_any_items(
            "reporter_agent", StateKeys.CANDIDATE_SCORES
        ),
        after_agent_callback=[
            require_output("reporter_agent", StateKeys.SHORTLIST_REPORT),
            _persist_report,
        ],
    )
