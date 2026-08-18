from google.adk.agents import LlmAgent

from src.agents.stage_guards import require_output
from src.config import OPENAI_MODEL
from src.domain.models import StateKeys

# No output_schema here: SearchPlan.query_params is an open dict, which cannot be
# expressed as a strict JSON schema. The plan is consumed as text by the sourcing
# agents, so the guard below is what keeps the stage honest.
_INSTRUCTION = (
    "You are a search strategy planner.\n\n"
    "HIRING REQUIREMENTS\n"
    "{hiring_requirements}\n\n"
    "LOCATION: {location}\n"
    "WORK MODE: {work_mode}\n\n"
    "Return ONLY a SearchPlan JSON object, no prose and no markdown fences:\n"
    '  "sources" : always ["himalayas", "github", "tavily"]\n'
    '  "queries" : one object per source, each with\n'
    '      "source"       : the source name\n'
    '      "query_params" : the parameters that source needs\n'
    '      "rationale"    : why those parameters\n\n'
    "RULES\n"
    "- the himalayas query_params may only use the parameters its search_talent tool\n"
    "  accepts: keyword (a short free-text query such as 'python backend developer') and\n"
    "  country\n"
    "- work_mode 'remote'  -> no country in the himalayas query_params; the board is\n"
    "  remote-first, so the whole index already qualifies\n"
    "- work_mode 'hybrid'  -> the himalayas query_params MUST carry the location above as\n"
    "  country, and the rationale MUST note that geographic coverage is limited\n"
    "- the github query_params MUST target the primary required skill (for example\n"
    "  'language:python') so it can be used directly as a GitHub search query\n"
    "- the tavily query_params MUST aim at corroborating candidates found elsewhere\n"
)


def make_planner_agent(model: str | None = None) -> LlmAgent:
    from google.adk.models.lite_llm import LiteLlm

    return LlmAgent(
        name="planner_agent",
        model=LiteLlm(model=model or OPENAI_MODEL, reasoning_effort="none"),
        instruction=_INSTRUCTION,
        output_key=StateKeys.SEARCH_PLAN,
        after_agent_callback=require_output("planner_agent", StateKeys.SEARCH_PLAN),
    )


planner_agent = make_planner_agent()
