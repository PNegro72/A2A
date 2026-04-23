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


# ── Requeridas ────────────────────────────────────────────────────────────────
GOOGLE_API_KEY       = require_env("GOOGLE_API_KEY")
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
OUTPUT_DIR = Path(os.environ.get("KIT_OUTPUT_DIR", "./output/kits"))
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
