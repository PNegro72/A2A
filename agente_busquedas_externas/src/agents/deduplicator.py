import json
import logging

from google.adk.agents import LlmAgent
from google.adk.agents.callback_context import CallbackContext
from pydantic import ValidationError

from src.agents.stage_guards import PipelineStageError, require_any_items, require_output
from src.config import OPENAI_MODEL
from src.domain.models import (
    CandidateIdentity,
    CandidateLead,
    DedupResult,
    StateKeys,
)
from src.persistence.repositories import CandidateRepository

logger = logging.getLogger("google_adk." + __name__)

_INSTRUCTION = (
    "You are a deduplication specialist. You decide which leads describe the same "
    "human being.\n\n"
    "LEADS FROM HIMALAYAS (JSON)\n"
    "{leads_himalayas}\n\n"
    "LEADS FROM GITHUB (JSON)\n"
    "{leads_github}\n\n"
    "LEADS FROM WEB RESEARCH (JSON)\n"
    "{leads_tavily}\n\n"
    "CANONICAL ID RULES\n"
    "- The lead (or any of its siblings) exposes a GitHub identity -> 'gh:<username>'\n"
    "- Otherwise -> 'himalayas:<raw_id>'\n"
    "Leads describing the same person MUST collapse into exactly one identity, and "
    "every input lead MUST appear in exactly one identity.\n\n"
    "OUTPUT CONTRACT — enforced by a strict JSON schema; a response that does not match "
    "is rejected.\n"
    'Return a JSON object with a single key "identities" holding a list of objects:\n'
    '  "canonical_id" : as per the rules above\n'
    '  "github_url"   : the candidate\'s GitHub profile URL if any lead has one, else null\n'
    '  "merged_leads" : the FULL lead objects that belong to this person, copied\n'
    "                   verbatim from the input — same source, raw_id, name, headline,\n"
    "                   profile_url, github_url and the complete evidence list.\n\n"
    "RULES\n"
    "- Copy evidence objects verbatim, including their source_url and source_type. Never\n"
    "  summarise them into strings, never drop them, never swap one candidate's URL for\n"
    "  another's: the score is computed only from this evidence.\n"
    "- Do not invent leads or identities that are not in the input.\n"
)


def make_deduplicator_agent(
    candidate_repo: CandidateRepository,
    model: str | None = None,
) -> LlmAgent:
    from google.adk.models.lite_llm import LiteLlm

    def _to_domain_lead(canonical_id: str, raw_lead: dict) -> CandidateLead:
        try:
            return CandidateLead.model_validate(raw_lead)
        except ValidationError as exc:
            # The wire schema already guarantees the shape, so getting here means
            # the model produced a lead that violates the evidence contract
            # (typically a missing or non-http source_url). Fail loudly instead
            # of dropping the candidate on the floor.
            raise PipelineStageError(
                f"deduplicator_agent produced an invalid lead for {canonical_id}: "
                f"{exc.errors(include_url=False)} — lead={json.dumps(raw_lead)[:400]}"
            ) from exc

    async def _persist_identities(callback_context: CallbackContext) -> None:
        """Persist the merged identities.

        Deterministic Python, not a tool call: passing whole lead lists as JSON
        string arguments used to get truncated by the model, which lost
        candidates at random.
        """
        raw = callback_context.state.get(StateKeys.CANDIDATE_IDENTITIES)
        if isinstance(raw, str):
            raw = json.loads(raw)
        result = DedupResult.model_validate(raw)

        for identity in result.identities:
            leads = [
                _to_domain_lead(identity.canonical_id, lead.model_dump())
                for lead in identity.merged_leads
            ]
            existing = await candidate_repo.get(identity.canonical_id)
            if existing:
                # Keep previously known leads that this run did not re-observe.
                seen = {(lead.source, lead.raw_id) for lead in leads}
                leads += [
                    lead
                    for lead in existing.merged_leads
                    if (lead.source, lead.raw_id) not in seen
                ]
            merged = CandidateIdentity(
                canonical_id=identity.canonical_id,
                merged_leads=leads,
                github_url=identity.github_url,
            )
            if existing:
                merged.first_seen_at = existing.first_seen_at
            await candidate_repo.upsert(merged)
        logger.info(
            "[deduplicator] persisted %d identities (%d leads total)",
            len(result.identities),
            sum(len(i.merged_leads) for i in result.identities),
        )

    return LlmAgent(
        name="deduplicator_agent",
        model=LiteLlm(model=model or OPENAI_MODEL, reasoning_effort="none"),
        instruction=_INSTRUCTION,
        output_schema=DedupResult,
        output_key=StateKeys.CANDIDATE_IDENTITIES,
        before_agent_callback=require_any_items(
            "deduplicator_agent",
            StateKeys.LEADS_HIMALAYAS,
            StateKeys.LEADS_GITHUB,
            StateKeys.LEADS_TAVILY,
        ),
        after_agent_callback=[
            require_output("deduplicator_agent", StateKeys.CANDIDATE_IDENTITIES),
            _persist_identities,
        ],
    )
