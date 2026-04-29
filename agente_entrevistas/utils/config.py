"""
Configuración central del agente.
Carga variables de entorno y expone constantes usadas por los tools.
"""

import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv(Path(__file__).parent.parent / ".env")


def require_env(key: str) -> str:
    val = os.environ.get(key)
    if not val:
        raise EnvironmentError(
            f"Variable de entorno requerida no encontrada: {key}\n"
            f"Asegurate de tenerla en tu .env o en el entorno del proceso."
        )
    return val


# ── LLM (OpenAI vía LiteLLM, mismo patrón que el resto de los agentes) ───────
OPENAI_API_KEY = require_env("OPENAI_API_KEY")
OPENAI_MODEL   = require_env("OPENAI_MODEL")

# ── Server (FastAPI / uvicorn) ───────────────────────────────────────────────
HOST      = require_env("HOST")
PORT      = int(require_env("PORT"))
LOG_LEVEL = require_env("LOG_LEVEL")

# ── Supabase ──────────────────────────────────────────────────────────────────
SUPABASE_URL         = require_env("SUPABASE_URL")
SUPABASE_SERVICE_KEY = require_env("SUPABASE_SERVICE_KEY")

# ── Microsoft 365 (email) ────────────────────────────────────────────────────
MS_TENANT_ID     = require_env("MS_TENANT_ID")
MS_CLIENT_ID     = require_env("MS_CLIENT_ID")
MS_CLIENT_SECRET = require_env("MS_CLIENT_SECRET")
MS_SENDER_EMAIL  = require_env("MS_SENDER_EMAIL")

# ── Opcionales ────────────────────────────────────────────────────────────────
TAVILY_API_KEY = os.environ.get("TAVILY_API_KEY")
SERPER_API_KEY = os.environ.get("SERPER_API_KEY")

# ── Rutas de output ───────────────────────────────────────────────────────────
OUTPUT_DIR = Path(require_env("KIT_OUTPUT_DIR"))
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
