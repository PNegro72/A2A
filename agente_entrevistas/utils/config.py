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


# ── LLM (OpenAI vía LiteLLM) ─────────────────────────────────────────────────
OPENAI_API_KEY = require_env("OPENAI_API_KEY")
OPENAI_MODEL   = require_env("OPENAI_MODEL")

# ── Server (FastAPI / uvicorn) ───────────────────────────────────────────────
HOST      = require_env("HOST")
PORT      = int(require_env("PORT"))
LOG_LEVEL = require_env("LOG_LEVEL")

# ── Supabase (opcional) ───────────────────────────────────────────────────────
# La persistencia en Supabase nunca se implementó: no existe ningún cliente
# Supabase en el código. Se dejan como opcionales para no bloquear el arranque.
SUPABASE_URL         = os.environ.get("SUPABASE_URL")
SUPABASE_SERVICE_KEY = os.environ.get("SUPABASE_SERVICE_KEY")

# ── Microsoft 365 (opcional) ─────────────────────────────────────────────────
# El envío de email pasó de MS Graph a Mailtrap (commit ce365f0), así que las
# credenciales MS_TENANT_ID / MS_CLIENT_ID / MS_CLIENT_SECRET ya no se usan.
# MS_SENDER_EMAIL sigue usándose como remitente en tools/crear_borrador_email.py
# (que ya tiene su propio fallback), por eso también es opcional.
MS_TENANT_ID     = os.environ.get("MS_TENANT_ID")
MS_CLIENT_ID     = os.environ.get("MS_CLIENT_ID")
MS_CLIENT_SECRET = os.environ.get("MS_CLIENT_SECRET")
MS_SENDER_EMAIL  = os.environ.get("MS_SENDER_EMAIL")

# ── Opcionales ────────────────────────────────────────────────────────────────
TAVILY_API_KEY = os.environ.get("TAVILY_API_KEY")
SERPER_API_KEY = os.environ.get("SERPER_API_KEY")

# ── Rutas de output ───────────────────────────────────────────────────────────
OUTPUT_DIR = Path(require_env("KIT_OUTPUT_DIR"))
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
