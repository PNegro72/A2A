import asyncio
import os

import uvicorn
from dotenv import load_dotenv
from google.adk.a2a.utils.agent_to_a2a import to_a2a

from src.agents.orchestrator import create_orchestrator_agent
from src.persistence.db import get_connection
from src.persistence.sqlite_repos import (
    SQLiteCandidateRepository,
    SQLitePipelineRunRepository,
    SQLiteShortlistReportRepository,
)

load_dotenv()

_HOST = os.getenv("HOST", "0.0.0.0")
_PORT = int(os.getenv("PORT", "8080"))


async def build_app():
    db = await get_connection()
    candidate_repo = SQLiteCandidateRepository(db)
    pipeline_repo = SQLitePipelineRunRepository(db)
    report_repo = SQLiteShortlistReportRepository(db)

    agent = create_orchestrator_agent(candidate_repo, pipeline_repo, report_repo)
    return to_a2a(agent, host=_HOST, port=_PORT)


async def main() -> None:
    app = await build_app()
    config = uvicorn.Config(app, host=_HOST, port=_PORT, log_level="info")
    server = uvicorn.Server(config)
    await server.serve()


if __name__ == "__main__":
    asyncio.run(main())
