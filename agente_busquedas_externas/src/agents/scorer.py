from google.adk.agents import LlmAgent

from src.config import OPENAI_MODEL
from src.domain.models import StateKeys


def make_scorer_agent(model: str | None = None) -> LlmAgent:
    from google.adk.models.lite_llm import LiteLlm

    return LlmAgent(
        name="scorer_agent",
        model=LiteLlm(model=model or OPENAI_MODEL),
        instruction=(
            "You are a candidate scoring specialist.\n"
            f"Read state['{StateKeys.CANDIDATE_IDENTITIES}'] and "
            f"state['{StateKeys.HIRING_REQUIREMENTS}'].\n\n"
            "For each CandidateIdentity, produce a CandidateScore dict with EXACTLY:\n"
            '  "candidate_id": str — the canonical_id\n'
            '  "score": float 0.0-1.0 based on evidence match\n'
            '  "reasoning": str — explain which requirements are met and which are missing\n'
            '  "risk_flags": list of RiskFlag dicts, each with:\n'
            '      "type": one of "data-quality", "compliance", "weak-signal", "conflict"\n'
            '      "description": str\n'
            '      "severity": one of "low", "medium", "high"\n\n'
            "STRICT EVIDENCE RULES:\n"
            "- Only use data present in the candidate's CandidateEvidence records\n"
            "- NEVER generate or infer facts not present in evidence\n"
            "- If seniority is from an evidence item with inferred=True, ADD a "
            "  RiskFlag(type='weak-signal', severity='low', description=inference_basis)\n"
            "- If a required skill has no supporting evidence, penalize the score\n"
            "- Score >= 0.7 means strong match; 0.4-0.7 partial; < 0.4 weak\n\n"
            "Example RiskFlag:\n"
            '  {"type": "weak-signal", "description": "Seniority inferred from '
            'years since first commit", "severity": "low"}\n\n'
            "Write the JSON list of CandidateScore dicts to "
            f"state['{StateKeys.CANDIDATE_SCORES}']."
        ),
        output_key=StateKeys.CANDIDATE_SCORES,
    )


scorer_agent = make_scorer_agent()