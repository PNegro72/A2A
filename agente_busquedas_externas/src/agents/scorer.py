from google.adk.agents import LlmAgent

from src.domain.models import StateKeys

def make_scorer_agent() -> LlmAgent:
    return LlmAgent(
        name="scorer_agent",
        model="gemini-2.0-flash",
        instruction=(
        "You are a candidate scoring specialist.\n"
        f"Read state['{StateKeys.CANDIDATE_IDENTITIES}'] and "
        f"state['{StateKeys.HIRING_REQUIREMENTS}'].\n\n"
        "For each CandidateIdentity, score them against the hiring requirements:\n"
        "  score: float 0.0-1.0 based on evidence match\n"
        "  reasoning: explain which requirements are met and which are missing\n"
        "  risk_flags: list of RiskFlags\n\n"
        "STRICT EVIDENCE RULES:\n"
        "- Only use data present in the candidate's CandidateEvidence records\n"
        "- NEVER generate or infer facts not present in evidence\n"
        "- If seniority is from an evidence item with inferred=True, ADD a "
        "  RiskFlag(type='weak-signal', severity='low', description=inference_basis)\n"
        "- If a required skill has no supporting evidence, penalize the score\n"
        "- Score >= 0.7 means strong match; 0.4-0.7 partial; < 0.4 weak\n\n"
        "Write the JSON list of CandidateScore objects to "
        f"state['{StateKeys.CANDIDATE_SCORES}']."
        ),
        output_key=StateKeys.CANDIDATE_SCORES,
    )


scorer_agent = make_scorer_agent()
