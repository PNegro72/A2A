from google.adk.agents import LlmAgent
from google.adk.tools import FunctionTool

from src.domain.models import CandidateIdentity, CandidateLead, StateKeys
from src.persistence.repositories import CandidateRepository


def make_deduplicator_agent(candidate_repo: CandidateRepository) -> LlmAgent:
    """Factory: returns a DeduplicatorAgent closed over the given repository."""

    async def lookup_candidate(canonical_id: str) -> dict | None:
        """Check if a candidate already exists in the database."""
        identity = await candidate_repo.get(canonical_id)
        return identity.model_dump(mode="json") if identity else None

    async def save_candidate(canonical_id: str, leads_json: str) -> str:
        """Upsert a CandidateIdentity with merged leads."""
        import json
        leads = [CandidateLead(**lead) for lead in json.loads(leads_json)]
        identity = CandidateIdentity(canonical_id=canonical_id, merged_leads=leads)
        await candidate_repo.upsert(identity)
        return f"saved:{canonical_id}"

    return LlmAgent(
        name="deduplicator_agent",
        model="gemini-2.0-flash",
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
