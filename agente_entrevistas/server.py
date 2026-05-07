"""
Servidor HTTP para el agente entrevistas.

Expone POST /a2a/entrevistas aceptando el payload JSON plano que envía
el orchestrator (ej: {"action": "preparar_entrevista", "candidato_id": "...",
"proceso_id": "...", "enviar_email": false}) y retorna el output del agente ADK.

Lee toda la configuración del .env (HOST, PORT, LOG_LEVEL, CLAUDE_*, SUPABASE_*,
MS_*, KIT_OUTPUT_DIR, TAVILY_API_KEY/SERPER_API_KEY). Si alguna variable falta,
el agente falla al arrancar (fail-fast en utils/config.py).

Correr con (desde la carpeta agente_entrevistas/):
    python server.py
"""

import json
import logging
import sys
import uuid
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Optional

import uvicorn
from dotenv import load_dotenv
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
from google.genai import types

# Permite importar `agente_entrevistas.*` cuando se ejecuta `python server.py`
# desde la carpeta del agente (Python solo agrega la carpeta del script a sys.path).
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

load_dotenv()

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger(__name__)

from agente_entrevistas.agent import root_agent  # noqa: E402
from agente_entrevistas.utils.config import HOST, LOG_LEVEL, PORT  # noqa: E402

APP_NAME = "entrevistas"
USER_ID = "orchestrator"

session_service: Optional[InMemorySessionService] = None
runner: Optional[Runner] = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    global session_service, runner
    session_service = InMemorySessionService()
    runner = Runner(agent=root_agent, app_name=APP_NAME, session_service=session_service)
    logger.info(
        "ENTREVISTAS agent listo en http://%s:%s/a2a/entrevistas",
        HOST, PORT,
    )
    yield


app = FastAPI(title="Entrevistas Agent", lifespan=lifespan)


@app.post("/a2a/entrevistas")
async def run_entrevistas(request: Request) -> JSONResponse:
    if session_service is None or runner is None:
        return JSONResponse(
            {"status": "error", "message": "Agente todavía inicializando"},
            status_code=503,
        )

    try:
        payload = await request.json()
    except json.JSONDecodeError as exc:
        logger.warning("JSON inválido en request: %s", exc)
        return JSONResponse(
            {"status": "error", "message": "Payload JSON inválido"},
            status_code=400,
        )
    except Exception:
        logger.exception("Error inesperado parseando el payload")
        return JSONResponse(
            {"status": "error", "message": "Error procesando request"},
            status_code=400,
        )

    logger.info("Request recibido: action=%s", payload.get("action"))

    input_text = json.dumps(payload, ensure_ascii=False)

    session_id = f"req_{uuid.uuid4().hex}"
    await session_service.create_session(app_name=APP_NAME, user_id=USER_ID, session_id=session_id)

    content = types.Content(role="user", parts=[types.Part(text=input_text)])

    final_text = None
    try:
        async for event in runner.run_async(user_id=USER_ID, session_id=session_id, new_message=content):
            if event.is_final_response() and event.content and event.content.parts:
                final_text = event.content.parts[0].text
                break
    except Exception as exc:
        logger.exception("Error ejecutando agente")
        return JSONResponse({"status": "error", "message": str(exc)}, status_code=500)
    finally:
        try:
            await session_service.delete_session(
                app_name=APP_NAME, user_id=USER_ID, session_id=session_id,
            )
        except Exception:
            logger.exception("No se pudo limpiar la sesión %s", session_id)

    if not final_text:
        return JSONResponse({"status": "error", "message": "El agente no retornó respuesta"}, status_code=500)

    # El agente de entrevistas no usa output_schema (a diferencia de busquedas/jd):
    # retorna texto plano o JSON según el flujo. Devolvemos JSON parseado si pinta JSON,
    # y si no, lo envolvemos en {status, result}.
    try:
        result = json.loads(final_text)
        if isinstance(result, dict):
            result.setdefault("status", "ok")
        return JSONResponse(result)
    except json.JSONDecodeError:
        return JSONResponse({"status": "ok", "result": final_text})


@app.get("/health")
def health():
    return {"status": "ok", "agent": APP_NAME}


if __name__ == "__main__":
    uvicorn.run(app, host=HOST, port=PORT, log_level=LOG_LEVEL)
