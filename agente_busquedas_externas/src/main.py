import asyncio

import uvicorn
from google.adk.a2a.utils.agent_to_a2a import to_a2a

from src.agents.orchestrator import create_orchestrator_agent
from src.config import HOST, LOG_LEVEL, PORT
from src.persistence.db import get_connection
from src.persistence.sqlite_repos import (
    SQLiteCandidateRepository,
    SQLitePipelineRunRepository,
    SQLiteShortlistReportRepository,
)


async def build_app():
    db = await get_connection()
    candidate_repo = SQLiteCandidateRepository(db)
    pipeline_repo = SQLitePipelineRunRepository(db)
    report_repo = SQLiteShortlistReportRepository(db)

    agent = create_orchestrator_agent(candidate_repo, pipeline_repo, report_repo)
    return to_a2a(agent, host=HOST, port=PORT)


async def main() -> None:
    app = await build_app()
    config = uvicorn.Config(app, host=HOST, port=PORT, log_level=LOG_LEVEL.lower())
    server = uvicorn.Server(config)
    await server.serve()


if __name__ == "__main__":
    asyncio.run(main())