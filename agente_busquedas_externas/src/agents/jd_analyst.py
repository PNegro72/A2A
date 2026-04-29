from google.adk.agents import LlmAgent

from src.domain.models import StateKeys

def make_jd_analyst_agent() -> LlmAgent:
    return LlmAgent(
        name="jd_analyst_agent",
        model="gemini-2.0-flash",
        instruction=(
        "You are a job description analyst.\n"
        f"Read state['{StateKeys.JOB_DESCRIPTION}'], state['{StateKeys.LOCATION}'], "
        f"and state['{StateKeys.WORK_MODE}'].\n"
        "Extract structured hiring requirements and write them as a JSON object to "
        f"state['{StateKeys.HIRING_REQUIREMENTS}'] with this shape:\n"
        "  required_skills: list[str]\n"
        "  preferred_skills: list[str]\n"
        "  seniority: 'junior'|'mid'|'senior'|'staff'  (default 'mid' if unclear)\n"
        "  location_constraint: str | null\n"
        "  work_mode: same value as state['work_mode']\n"
        "  domain: str (e.g. 'backend Python', 'frontend React')\n\n"
        "If seniority cannot be determined from the JD, default to 'mid' AND append a "
        f"RiskFlag(type='weak-signal', description='seniority inferred', severity='low') "
        f"to state['{StateKeys.RISK_FLAGS}'] (initialize as [] if not present).\n"
        "Never leave required_skills empty — extract at least the technologies mentioned."
        ),
        output_key=StateKeys.HIRING_REQUIREMENTS,
    )


jd_analyst_agent = make_jd_analyst_agent()
