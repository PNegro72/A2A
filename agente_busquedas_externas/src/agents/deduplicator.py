from google.adk.agents import LlmAgent
from google.adk.tools import FunctionTool

from src.config import OPENAI_MODEL
from src.domain.models import CandidateIdentity, CandidateLead, StateKeys
from src.persistence.repositories import CandidateRepository


def make_deduplicator_agent(
    candidate_repo: CandidateRepository,
    model: str | None = None,
) -> LlmAgent:
    from google.adk.models.lite_llm import LiteLlm

    async def lookup_candidate(canonical_id: str) -> dict | None:
        """Check if a candidate already exists in the database."""
        identity = await candidate_repo.get(canonical_id)
        return identity.model_dump(mode="json") if identity else None

    async def save_candidate(canonical_id: str, leads_json: str) -> str:
        """Upsert a CandidateIdentity with merged leads."""
        import json
        import logging

        from pydantic import ValidationError

        logger = logging.getLogger("google_adk." + __name__)

        try:
            raw = json.loads(leads_json)
        except json.JSONDecodeError as e:
            logger.warning(
                "save_candidate: invalid JSON for %s: %s. Data: %.300s",
                canonical_id, e, leads_json,
            )
            return f"skipped:{canonical_id}"
        # Normalise: if a single dict was passed instead of a list, wrap it
        raw_leads = raw if isinstance(raw, list) else [raw]
        leads: list[CandidateLead] = []
        for lead in raw_leads:
            if not isinstance(lead, dict):
                logger.warning(
                    "save_candidate: skipping non-dict lead element (type=%s): %s",
                    type(lead).__name__,
                    str(lead)[:200],
                )
                continue
            try:
                leads.append(CandidateLead.model_validate(lead))
            except ValidationError:
                logger.warning(
                    "save_candidate: skipping un-normalizable lead for %s: %.200s",
                    canonical_id, str(lead)[:200],
                    exc_info=True,
                )
                continue
        identity = CandidateIdentity(canonical_id=canonical_id, merged_leads=leads)
        await candidate_repo.upsert(identity)
        return f"saved:{canonical_id}"

    return LlmAgent(
        name="deduplicator_agent",
        # NOTA (2026-08-05): con varios candidatos, algunos tool calls a
        # save_candidate() llegan con leads_json truncado (JSONDecodeError,
        # capturado ahí — el candidato queda sin persistir en esa llamada,
        # aunque en la práctica suele reaparecer igual en el reporte final
        # vía el state de leads crudos). Probé parallel_tool_calls=False
        # pensando que era interferencia entre tool calls paralelos, pero el
        # truncado persistió igual — el modelo parece truncar el string JSON
        # largo dentro de un solo argumento, no por paralelismo. Sin fix
        # confirmado todavía; ver conversación del 2026-08-05 para detalle.
        model=LiteLlm(model=model or OPENAI_MODEL, reasoning_effort="none"),
        instruction=(
            "You are a deduplication specialist.\n"
            "Collect all leads from:\n"
            f"  state['{StateKeys.LEADS_HIMALAYAS}'],\n"
            f"  state['{StateKeys.LEADS_GITHUB}'],\n"
            f"  state['{StateKeys.LEADS_TAVILY}']\n"
            "For each lead that has a github_url, use the GitHub username as canonical_id "
            "(format: 'gh:<username>'). For leads without a github_url, use email if available, "
            "otherwise use 'himalayas:<raw_id>'.\n\n"
            "For each canonical_id:\n"
            "1. Call lookup_candidate(canonical_id) to check if it exists in the DB\n"
            "2. Merge all leads sharing that canonical_id into one CandidateIdentity\n"
            "3. Call save_candidate(canonical_id, leads_json) to persist\n\n"
            "Write the list of merged CandidateIdentity objects (as JSON) to "
            f"state['{StateKeys.CANDIDATE_IDENTITIES}'].\n"
            "A candidate appearing in multiple sources MUST produce exactly one entry."
        ),
        tools=[FunctionTool(lookup_candidate), FunctionTool(save_candidate)],
        output_key=StateKeys.CANDIDATE_IDENTITIES,
    )