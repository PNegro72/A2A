"""
Servidor HTTP para los agentes de Job Description.

Expone dos endpoints:
  - POST /a2a/job_description  → parsea una JD existente (texto libre) y la
    estructura en JobDescriptionEstructurada.
  - POST /a2a/redactar_jd      → recibe una request corta del usuario y genera
    una JD completa en JobDescriptionRedactada (con idioma detectado).

Requiere CLAUDE_API_KEY en .env. Host y puerto se configuran via
HOST y PORT (ver agentes/config/settings.py).

Correr con:
    python server.py
"""
##

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

# Importar los agentes
from agentes.config.settings import get_settings  # noqa: E402
from agentes.job_description.agent import root_agent as parser_agent  # noqa: E402
from agentes.redactar_jd.agent import root_agent as redactor_agent  # noqa: E402

PARSER_APP_NAME = "job_description"
REDACTOR_APP_NAME = "redactar_jd"
USER_ID = "orchestrator"

session_service: Optional[InMemorySessionService] = None
parser_runner: Optional[Runner] = None
redactor_runner: Optional[Runner] = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    global session_service, parser_runner, redactor_runner
    settings = get_settings()
    session_service = InMemorySessionService()
    parser_runner = Runner(
        agent=parser_agent, app_name=PARSER_APP_NAME, session_service=session_service
    )
    redactor_runner = Runner(
        agent=redactor_agent, app_name=REDACTOR_APP_NAME, session_service=session_service
    )
    logger.info(
        "JOB DESCRIPTION agents listos en http://%s:%s — endpoints: "
        "POST /a2a/job_description, POST /a2a/redactar_jd",
        settings.HOST, settings.PORT,
    )
    yield


app = FastAPI(title="Job Description Agent", lifespan=lifespan)


async def _run_agent(
    request: Request,
    runner: Optional[Runner],
    app_name: str,
) -> JSONResponse:
    """
    Lógica común para correr un LlmAgent ADK con el payload JSON del request:
    parsea el body, crea una sesión efímera, ejecuta el agente y devuelve
    el output (siempre JSON gracias al output_schema).
    """
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

    logger.info("[%s] Request recibido: action=%s", app_name, payload.get("action"))

    input_text = json.dumps(payload, ensure_ascii=False)

    session_id = f"req_{uuid.uuid4().hex}"
    await session_service.create_session(app_name=app_name, user_id=USER_ID, session_id=session_id)

    content = types.Content(role="user", parts=[types.Part(text=input_text)])

    final_text = None
    try:
        async for event in runner.run_async(user_id=USER_ID, session_id=session_id, new_message=content):
            if event.is_final_response() and event.content and event.content.parts:
                final_text = event.content.parts[0].text
                break
    except Exception as exc:
        logger.exception("Error ejecutando agente %s", app_name)
        return JSONResponse({"status": "error", "message": str(exc)}, status_code=500)
    finally:
        try:
            await session_service.delete_session(
                app_name=app_name, user_id=USER_ID, session_id=session_id,
            )
        except Exception:
            logger.exception("No se pudo limpiar la sesión %s", session_id)

    if not final_text:
        return JSONResponse({"status": "error", "message": "El agente no retornó respuesta"}, status_code=500)

    try:
        result = json.loads(final_text)
        if isinstance(result, dict):
            result.setdefault("status", "ok")
        return JSONResponse(result)
    except json.JSONDecodeError:
        return JSONResponse({"status": "ok", "result": final_text})


@app.post("/a2a/job_description")
async def run_job_description(request: Request) -> JSONResponse:
    """Parsea una JD existente (texto libre) en JobDescriptionEstructurada."""
    return await _run_agent(request, parser_runner, PARSER_APP_NAME)


@app.post("/a2a/redactar_jd")
async def run_redactar_jd(request: Request) -> JSONResponse:
    """
    Genera una JD completa a partir de una request corta del usuario.
    Payload esperado: {"action": "redactar_jd", "request": "<oración del usuario>"}.
    Retorna un JobDescriptionRedactada con idioma detectado (es/en),
    cantidad_candidatos parseada y la JD lista en `texto_completo` (Markdown).
    """
    return await _run_agent(request, redactor_runner, REDACTOR_APP_NAME)


@app.get("/health")
def health():
    return {"status": "ok", "agents": [PARSER_APP_NAME, REDACTOR_APP_NAME]}


if __name__ == "__main__":
    settings = get_settings()
    uvicorn.run(app, host=settings.HOST, port=settings.PORT, log_level=settings.LOG_LEVEL)