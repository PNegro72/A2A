import asyncio
import sys
from pathlib import Path

import uvicorn
from dotenv import load_dotenv

load_dotenv()

# observability.py is at the agente_busquedas_externas/ root; add it to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from observability import init_observability  # noqa: E402 — must precede google.adk
init_observability("busquedas_externas")

from google.adk.a2a.utils.agent_to_a2a import to_a2a  # noqa: E402

from src.agents.orchestrator import create_orchestrator_agent  # noqa: E402
from src.config import HOST, LOG_LEVEL, PORT  # noqa: E402
from src.persistence.db import get_connection  # noqa: E402
from src.persistence.sqlite_repos import (  # noqa: E402
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