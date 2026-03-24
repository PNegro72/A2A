import os
import sys
import subprocess
import mcp.client.stdio as mcp_stdio

from dotenv import load_dotenv
from langchain.agents import create_agent
from langchain_mcp_adapters.client import MultiServerMCPClient
from langchain_mcp_adapters.sessions import StdioConnection
from langchain_openai import ChatOpenAI

try:
    from mcp.os.win32.utilities import _create_windows_fallback_process
except Exception:  # pragma: no cover
    _create_windows_fallback_process = None

class ProviderAgent:
    _mcp_stdio_patched = False

    def __init__(self) -> None:
        load_dotenv(override=True)

        # Parche idempotente para notebooks en Windows: evita stderr con fileno no soportado.
        if not ProviderAgent._mcp_stdio_patched:
            _orig_create = mcp_stdio.create_windows_process

            async def _patched_create_windows_process(command, args, env=None, errlog=None, cwd=None):
                try:
                    return await _orig_create(command, args, env=env, errlog=None, cwd=cwd)
                except Exception:
                    if _create_windows_fallback_process is not None:
                        return await _create_windows_fallback_process(
                            command, args, env=env, errlog=subprocess.DEVNULL, cwd=cwd
                        )
                    return await _orig_create(
                        command, args, env=env, errlog=subprocess.DEVNULL, cwd=cwd
                    )

            mcp_stdio.create_windows_process = _patched_create_windows_process
            ProviderAgent._mcp_stdio_patched = True

        self.mcp_client = MultiServerMCPClient(
            {
                "find_healthcare_providers": StdioConnection(
                    transport="stdio",
                    command=sys.executable,
                    args=["mcpserver.py"],
                )
            }
        )

        self.agent = None

    async def initialize(self):
        """Initialize the agent asynchronously."""
        openai_api_key = os.getenv("OPENAI_API_KEY")
        openai_api_base = os.getenv("OPENAI_BASE_URL")
        if not openai_api_key:
            raise ValueError("OPENAI_API_KEY not set in .env")
        if not openai_api_base:
            raise ValueError("OPENAI_BASE_URL not set in .env")

        tools = await self.mcp_client.get_tools()
        self.agent = create_agent(
            ChatOpenAI(
                model="gpt-4.1-mini",
                openai_api_key=openai_api_key,
                openai_api_base=openai_api_base
            ),
            tools,
            name="HealthcareProviderAgent",
            system_prompt="""Your task is to find and list providers using 
            the available MCP tools (for example, list_doctors) based on the user's query.
            Only use providers based on the response from the tool. Output 
            the information in a table.""",
        )
        return self

    async def answer_query(self, prompt: str) -> str:
        if self.agent is None:
            raise RuntimeError("""Agent not initialized. Call initialize() first.""")

        response = await self.agent.ainvoke(
            {
                "messages": [
                    {
                        "role": "user",
                        "content": prompt,
                    }
                ]
            }
        )
        return response["messages"][-1].content
