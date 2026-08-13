from google.adk.agents import LlmAgent

from src.agents.stage_guards import require_any_items, require_output
from src.config import OPENAI_MODEL
from src.domain.models import ScoringResult, StateKeys

_INSTRUCTION = (
    "You are a candidate scoring specialist. You score strictly on observable "
    "evidence.\n\n"
    "HIRING REQUIREMENTS\n"
    "{hiring_requirements}\n\n"
    "DEDUPLICATED CANDIDATES (JSON)\n"
    "{candidate_identities}\n\n"
    "OUTPUT CONTRACT — enforced by a strict JSON schema; a response that does not match "
    "is rejected.\n"
    'Return a JSON object with a single key "candidates" holding one object per '
    "identity:\n"
    '  "candidate_id" : the canonical_id of the identity\n'
    '  "score"        : float between 0.0 and 1.0\n'
    '  "reasoning"    : which requirements the evidence meets and which it does not\n'
    '  "risk_flags"   : list of objects, each with\n'
    '      "type"        : one of "data-quality", "compliance", "weak-signal", "conflict"\n'
    '      "description" : what the risk is\n'
    '      "severity"    : one of "low", "medium", "high"\n'
    '  "merged_leads" : the identity\'s merged_leads copied VERBATIM, including every\n'
    "                   evidence object with its source_url and source_type. The\n"
    "                   entrevistas agent builds the interview kit from this, so it must\n"
    "                   not be omitted, trimmed or summarised.\n\n"
    "STRICT EVIDENCE RULES\n"
    "- Score only from facts present in the candidate's evidence objects.\n"
    "- Never introduce a fact that no evidence object supports.\n"
    "- A required skill with no supporting evidence lowers the score.\n"
    '- Evidence with inferred=true justifies a "weak-signal" risk flag whose description\n'
    "  is that item's inference_basis.\n"
    "- >= 0.7 strong match, 0.4-0.7 partial, < 0.4 weak. Score every identity, including\n"
    "  weak ones — filtering is the reporter's job.\n"
)


def make_scorer_agent(model: str | None = None) -> LlmAgent:
    from google.adk.models.lite_llm import LiteLlm

    return LlmAgent(
        name="scorer_agent",
        model=LiteLlm(model=model or OPENAI_MODEL, reasoning_effort="none"),
        instruction=_INSTRUCTION,
        output_schema=ScoringResult,
        output_key=StateKeys.CANDIDATE_SCORES,
        before_agent_callback=require_any_items(
            "scorer_agent", StateKeys.CANDIDATE_IDENTITIES
        ),
        after_agent_callback=require_output("scorer_agent", StateKeys.CANDIDATE_SCORES),
    )


scorer_agent = make_scorer_agent()
