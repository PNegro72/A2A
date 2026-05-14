from __future__ import annotations

import os

import litellm
from dotenv import load_dotenv

load_dotenv(override=True)

# --- Rate Limit Retry Configuration ---
# OpenAI free tier has 3 RPM for gpt-4o-mini. The pipeline runs 7+ agents
# in sequence, each making API calls. Retry with exponential backoff.
litellm.num_retries = 5
litellm.request_timeout = 120
os.environ.setdefault("LITELLM_RETRY_AFTER_MAX_WAIT", "60")

HOST = os.environ.get("HOST", "0.0.0.0")
PORT = int(os.environ.get("BUSQUEDAS_EXTERNAS_AGENT_PORT", "8080"))
LOG_LEVEL = os.environ.get("LOG_LEVEL", "INFO").upper()

OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY", "")
OPENAI_MODEL = os.environ.get("OPENAI_MODEL", "openai/gpt-4.1")
OPENAI_BASE_URL = os.environ.get("OPENAI_BASE_URL", "")

# LiteLLM reads OPENAI_API_KEY and OPENAI_API_BASE from environment.
# Forward base_url so custom endpoints (Azure, proxies, etc.) work.
if OPENAI_BASE_URL:
    os.environ["OPENAI_API_BASE"] = OPENAI_BASE_URL

DB_PATH = os.environ.get("DB_PATH", "agente_busquedas_externas.db")

GITHUB_TOKEN = os.environ.get("GITHUB_TOKEN", "")
TAVILY_API_KEY = os.environ.get("TAVILY_API_KEY", "")

if not OPENAI_API_KEY:
    raise ValueError("OPENAI_API_KEY is required but not set in environment")