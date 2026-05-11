"""
Console entry point for the Recruiting Orchestrator.

Usage (from inside the orchestrator/ folder):
    python main.py

Conversation state (session history) is preserved across turns via
InMemorySessionService, so context like previously proposed slots
is available for follow-up messages within a session.
"""

import asyncio
import logging
import os
import sys

from dotenv import load_dotenv

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)

# Validate required environment variables before importing the agent
# (the agent calls load_registry() at import time, which needs env vars)
_missing = [v for v in ("CLAUDE_API_KEY",) if not os.getenv(v)]
if _missing:
    logging.error("Missing required environment variables: %s", _missing)
    print(
        f"\n[ERROR] Missing environment variables: {', '.join(_missing)}\n"
        "  1. Add CLAUDE_API_KEY=<tu_clave> en el archivo .env\n"
    )
    sys.exit(1)

from google.adk.runners import Runner  # noqa: E402
from google.adk.sessions import InMemorySessionService  # noqa: E402
from google.genai import types  # noqa: E402

from agent import root_agent  # noqa: E402

APP_NAME = "recruiting_orchestrator"
USER_ID = "local_user"
SESSION_ID = "local_session"


async def main() -> None:
    session_service = InMemorySessionService()
    await session_service.create_session(
        app_name=APP_NAME, user_id=USER_ID, session_id=SESSION_ID
    )
    runner = Runner(agent=root_agent, app_name=APP_NAME, session_service=session_service)

    print("\nRecruiting Orchestrator ready. Type 'exit' to quit.\n")

    while True:
        try:
            user_input = input("You: ").strip()
        except (KeyboardInterrupt, EOFError):
            print("\nExiting.")
            break

        if user_input.lower() in {"exit", "quit"}:
            print("Goodbye.")
            break
        if not user_input:
            continue

        content = types.Content(role="user", parts=[types.Part(text=user_input)])

        try:
            async for event in runner.run_async(
                user_id=USER_ID, session_id=SESSION_ID, new_message=content
            ):
                if event.is_final_response() and event.content and event.content.parts:
                    print(f"Agent: {event.content.parts[0].text}\n")
        except Exception as exc:  # noqa: BLE001
            logging.error("Error during agent execution: %s", exc)
            print(f"[Error: {exc}]\n")


if __name__ == "__main__":
    asyncio.run(main())
