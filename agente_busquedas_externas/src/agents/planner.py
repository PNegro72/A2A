from google.adk.agents import LlmAgent

from src.domain.models import StateKeys

def make_planner_agent() -> LlmAgent:
    return LlmAgent(
        name="planner_agent",
        model="gemini-2.0-flash",
        instruction=(
        "You are a search strategy planner.\n"
        f"Read state['{StateKeys.HIRING_REQUIREMENTS}'] for skills, seniority, "
        f"location_constraint, and work_mode.\n"
        "Build a SearchPlan JSON object and write it to "
        f"state['{StateKeys.SEARCH_PLAN}'] with this shape:\n"
        "  sources: list[str]  — always ['himalayas', 'github', 'tavily'] for v0\n"
        "  queries: list of SourceQuery objects, one per source:\n"
        "    source: str\n"
        "    query_params: dict  — tailored params for that source\n"
        "    rationale: str\n\n"
        "Rules:\n"
        "- If work_mode='remote': Himalayas query MUST include remote=True\n"
        "- If work_mode='hybrid': Himalayas query MUST include location from "
        "  state['location']; add a caveat in rationale about limited geo coverage\n"
        "- GitHub query should target the primary skill in required_skills\n"
        "- Tavily query should focus on verifying candidates found by other sources"
        ),
        output_key=StateKeys.SEARCH_PLAN,
    )


planner_agent = make_planner_agent()
