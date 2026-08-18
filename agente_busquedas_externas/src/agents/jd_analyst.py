from google.adk.agents import LlmAgent

from src.agents.stage_guards import require_output
from src.config import OPENAI_MODEL
from src.domain.models import HiringRequirements, StateKeys

_INSTRUCTION = (
    "You are a job description analyst.\n\n"
    "JOB DESCRIPTION\n"
    "{job_description}\n\n"
    "LOCATION: {location}\n"
    "WORK MODE: {work_mode}\n\n"
    "Extract the hiring requirements.\n"
    "OUTPUT CONTRACT — enforced by a strict JSON schema; a response that does not match "
    "is rejected.\n"
    "Return a JSON object with these keys:\n"
    "  required_skills     : list of strings — never empty; at minimum every technology\n"
    "                        named in the job description\n"
    "  preferred_skills    : list of strings, possibly empty\n"
    "  seniority           : one of 'junior', 'mid', 'senior', 'staff' — use 'mid' when\n"
    "                        the description does not say\n"
    "  location_constraint : the location above when it constrains the search, else null\n"
    "  work_mode           : exactly the work mode above\n"
    "  domain              : short domain label, e.g. 'backend Python', 'frontend React'\n"
)


def make_jd_analyst_agent(model: str | None = None) -> LlmAgent:
    from google.adk.models.lite_llm import LiteLlm

    return LlmAgent(
        name="jd_analyst_agent",
        model=LiteLlm(model=model or OPENAI_MODEL, reasoning_effort="none"),
        instruction=_INSTRUCTION,
        output_schema=HiringRequirements,
        output_key=StateKeys.HIRING_REQUIREMENTS,
        after_agent_callback=require_output(
            "jd_analyst_agent", StateKeys.HIRING_REQUIREMENTS
        ),
    )


jd_analyst_agent = make_jd_analyst_agent()
