"""One-shot MCP tool calls over short-lived streamable-HTTP sessions.

ADK's ``McpToolset`` holds a single session open for the lifetime of the agent.
Both remote sourcing servers used here drop that session mid-run — the log shows
``Error on session runner task: unhandled errors in a TaskGroup`` — and every
subsequent tool call then blocks until the read timeout and takes the whole
pipeline down with it (observed: a 300s stall followed by a 500).

Giving each call its own session costs a couple of seconds of connect time and
buys three things: a dropped connection can only affect the call that hit it,
the timeout is per call, and a source that is down degrades the shortlist
instead of aborting the run.
"""

from __future__ import annotations

import logging
from datetime import timedelta
from typing import Any

from mcp import ClientSession
from mcp.client.streamable_http import streamablehttp_client

logger = logging.getLogger("google_adk." + __name__)

DEFAULT_TIMEOUT_SECONDS = 30.0
DEFAULT_ATTEMPTS = 2


async def _call_once(
    url: str, tool: str, args: dict[str, Any], timeout: float
) -> str:
    read_timeout = timedelta(seconds=timeout)
    async with streamablehttp_client(url, timeout=read_timeout) as (read, write, _):
        async with ClientSession(read, write) as session:
            await session.initialize()
            result = await session.call_tool(
                tool, args, read_timeout_seconds=read_timeout
            )
    text = "\n".join(
        getattr(part, "text", "") or "" for part in result.content
    ).strip()
    if result.isError:
        raise RuntimeError(f"MCP tool {tool} reported an error: {text[:300]}")
    return text


async def call_mcp_tool(
    url: str,
    tool: str,
    args: dict[str, Any],
    *,
    timeout: float = DEFAULT_TIMEOUT_SECONDS,
    attempts: int = DEFAULT_ATTEMPTS,
) -> dict[str, Any]:
    """Call a single MCP tool and return its text payload.

    Returns ``{"result": <text>}`` on success, or
    ``{"error": <message>, "status": "unavailable"}`` once the attempts are
    exhausted, so the calling agent can report a data-quality gap rather than
    raising through the pipeline.
    """
    last_error: Exception | None = None
    for attempt in range(1, attempts + 1):
        try:
            return {"result": await _call_once(url, tool, args, timeout)}
        except Exception as exc:  # noqa: BLE001 — reported back to the agent
            last_error = exc
            logger.warning(
                "MCP %s attempt %d/%d failed: %s: %s",
                tool,
                attempt,
                attempts,
                type(exc).__name__,
                exc,
            )
    return {"error": f"{type(last_error).__name__}: {last_error}", "status": "unavailable"}
