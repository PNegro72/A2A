"""
HTTP server for the agente_busquedas_externas agent.

Exposes POST /a2a/busquedas_externas accepting a JSON payload from the SAPE
orchestrator and returning a candidate shortlist report.

Also exposes GET /health for readiness checks.

Requires OPENAI_API_KEY, TAVILY_API_KEY in .env.
Host and port configured via HOST and BUSQUEDAS_EXTERNAS_AGENT_PORT.

Run with:
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

load_dotenv(override=True)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)

sys.path.insert(0, ".")

from src.agents.orchestrator import create_orchestrator_agent
from src.config import HOST, LOG_LEVEL, PORT
from src.persistence.db import get_connection
from src.persistence.sqlite_repos import (
    SQLiteCandidateRepository,
    SQLitePipelineRunRepository,
    SQLiteShortlistReportRepository,
)

APP_NAME = "busquedas_externas"
USER_ID = "orchestrator"

session_service: Optional[InMemorySessionService] = None
runner: Optional[Runner] = None


def _translate_payload(payload: dict) -> str:
    """
    Translate the orchestrator's payload schema into the pipeline's internal format.

    The orchestrator sends:
        action, role_title, role_description, management_level, skills,
        location, work_mode, cantidad_candidatos

    The pipeline expects:
        job_description: str  (composed from role_title + role_description + skills),
        location: str,
        work_mode: str
    """
    role_title = payload.get("role_title", "")
    role_description = payload.get("role_description", "")
    management_level = payload.get("management_level", "")
    skills = payload.get("skills", [])
    location = payload.get("location", "anywhere")
    work_mode = payload.get("work_mode", "remote")

    skills_str = ", ".join(skills) if isinstance(skills, list) else str(skills)

    jd_parts = []
    if role_title:
        jd_parts.append(f"Title: {role_title}")
    if management_level:
        jd_parts.append(f"Level: {management_level}")
    if role_description:
        jd_parts.append(role_description)
    if skills_str:
        jd_parts.append(f"Required skills: {skills_str}")

    job_description = "\n".join(jd_parts) if jd_parts else "General software engineering position"

    return json.dumps(
        {
            "job_description": job_description,
            "location": location,
            "work_mode": work_mode,
        },
        ensure_ascii=False,
    )


@asynccontextmanager
async def lifespan(app: FastAPI):
    global session_service, runner

    db = await get_connection()
    candidate_repo = SQLiteCandidateRepository(db)
    pipeline_repo = SQLitePipelineRunRepository(db)
    report_repo = SQLiteShortlistReportRepository(db)

    agent = create_orchestrator_agent(candidate_repo, pipeline_repo, report_repo)
    session_service = InMemorySessionService()
    runner = Runner(agent=agent, app_name=APP_NAME, session_service=session_service)

    logger.info(
        "BUSQUEDAS EXTERNAS agent listo en http://%s:%s/a2a/busquedas_externas",
        HOST,
        PORT,
    )
    yield


app = FastAPI(title="Busquedas Externas Agent", lifespan=lifespan)


@app.post("/a2a/busquedas_externas")
async def run_busquedas_externas(request: Request) -> JSONResponse:
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

    action = payload.get("action")
    logger.info("Request recibido: action=%s", action)

    if action != "buscar_candidatos_externos":
        return JSONResponse(
            {
                "status": "error",
                "message": (
                    f"Acción desconocida: '{action}'. "
                    "Acción disponible: buscar_candidatos_externos"
                ),
            },
            status_code=400,
        )

    required_fields = ["role_title"]
    missing = [f for f in required_fields if not payload.get(f)]
    if missing:
        return JSONResponse(
            {
                "status": "error",
                "message": f"Campos requeridos faltantes: {', '.join(missing)}",
            },
            status_code=400,
        )

    input_text = _translate_payload(payload)

    session_id = f"req_{uuid.uuid4().hex}"
    await session_service.create_session(
        app_name=APP_NAME, user_id=USER_ID, session_id=session_id
    )

    content = types.Content(role="user", parts=[types.Part(text=input_text)])

    final_text = None
    try:
        async for event in runner.run_async(
            user_id=USER_ID, session_id=session_id, new_message=content
        ):
            if event.is_final_response() and event.content and event.content.parts:
                final_text = event.content.parts[0].text
                # Don't break — let the full pipeline run.
                # Capture the LAST final response (from the reporter agent).
    except BaseException as exc:
        # BaseException catches both Exception and Python 3.14 ExceptionGroup
        logger.exception("Error ejecutando agente")
        msg = str(exc)
        if hasattr(exc, "exceptions"):
            msg = "; ".join(str(e) for e in exc.exceptions)
        return JSONResponse(
            {"status": "error", "message": msg}, status_code=500
        )

    # Read the ShortlistReport from state — this is the authoritative output
    # of the reporter agent (output_key=StateKeys.SHORTLIST_REPORT).
    # The LLM's final_text may be a summary or description, not the JSON.
    report_data = None
    try:
        session = await session_service.get_session(
            app_name=APP_NAME, user_id=USER_ID, session_id=session_id
        )
        if session and session.state:
            report_data = session.state.get("shortlist_report")
    except Exception:
        logger.warning("Could not read shortlist_report from state", exc_info=True)

    try:
        await session_service.delete_session(
            app_name=APP_NAME, user_id=USER_ID, session_id=session_id
        )
    except Exception:
        logger.exception("No se pudo limpiar la sesión %s", session_id)

    if report_data:
        if isinstance(report_data, str):
            try:
                report_data = json.loads(report_data)
            except json.JSONDecodeError:
                logger.warning("shortlist_report is string but not valid JSON, len=%d", len(report_data))
        if isinstance(report_data, dict):
            report_data.setdefault("status", "exito")
            return JSONResponse(report_data)

    # Fallback: try to parse the LLM's text response
    if final_text:
        try:
            result = json.loads(final_text)
            if isinstance(result, dict):
                result.setdefault("status", "exito")
                return JSONResponse(result)
        except json.JSONDecodeError:
            logger.warning("LLM final_text is not valid JSON, len=%d: %.200s", len(final_text), final_text)
        return JSONResponse({"status": "exito", "result": final_text})

    return JSONResponse(
        {"status": "error", "message": "El agente no retornó respuesta"},
        status_code=500,
    )


@app.get("/health")
def health():
    return {"status": "ok", "agent": APP_NAME}


if __name__ == "__main__":
    uvicorn.run(app, host=HOST, port=PORT, log_level=LOG_LEVEL.lower())