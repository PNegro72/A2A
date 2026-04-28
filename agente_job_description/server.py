"""
Servidor HTTP para el agente job_description.

Expone POST /a2a/job_description aceptando el payload JSON plano
que envía el orchestrator (ej: {"action": "parsear_jd", "jd_texto": "..."})
y retorna el output del agente ADK.

Requiere OPENAI_API_KEY en .env. Host y puerto se configuran via
HOST y PORT (ver agentes/config/settings.py).

Correr con:
    python server.py
"""

import json
import logging
import sys
import uuid
from contextlib import asynccontextmanager
from typing import Optional

import uvicorn
from dotenv import load_dotenv
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
from google.genai import types

load_dotenv()

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger(__name__)

sys.path.insert(0, ".")

# Importar el agente
from agentes.config.settings import get_settings  # noqa: E402
from agentes.job_description.agent import root_agent  # noqa: E402

APP_NAME = "job_description"
USER_ID = "orchestrator"

session_service: Optional[InMemorySessionService] = None
runner: Optional[Runner] = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    global session_service, runner
    settings = get_settings()
    session_service = InMemorySessionService()
    runner = Runner(agent=root_agent, app_name=APP_NAME, session_service=session_service)
    logger.info(
        "JOB DESCRIPTION agent listo en http://%s:%s/a2a/job_description",
        settings.HOST, settings.PORT,
    )
    yield


app = FastAPI(title="Job Description Agent", lifespan=lifespan)


@app.post("/a2a/job_description")
async def run_job_description(request: Request) -> JSONResponse:
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

    # Convertir payload a texto para el agente
    input_text = json.dumps(payload, ensure_ascii=False)

    # Crear sesión única por request
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

    # El agente retorna JSON con output_schema=JobDescriptionEstructurada
    try:
        result = json.loads(final_text)
        result.setdefault("status", "ok")
        return JSONResponse(result)
    except json.JSONDecodeError:
        return JSONResponse({"status": "ok", "result": final_text})


@app.get("/health")
def health():
    return {"status": "ok", "agent": APP_NAME}


if __name__ == "__main__":
    settings = get_settings()
    uvicorn.run(app, host=settings.HOST, port=settings.PORT, log_level=settings.LOG_LEVEL)
