"""
Servidor HTTP del Orchestrator de Reclutamiento.

Expone los endpoints que el frontend PWA espera:
  POST /chat              → inicia un mensaje, devuelve request_id
  GET  /chat/stream/{id}  → SSE con pasos intermedios + respuesta final

Cómo correr:
    python server.py
    # Escucha en http://${HOST}:${PORT} (definidos en .env)
"""

import asyncio
import json
import logging
import os
import sys
import uuid
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from typing import AsyncGenerator

import uvicorn
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
from google.genai import types
from pydantic import BaseModel

load_dotenv()
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)

sys.path.insert(0, ".")

from agent import root_agent  # noqa: E402

# ---------------------------------------------------------------------------
# Constantes ADK
# ---------------------------------------------------------------------------
APP_NAME = "recruiting_orchestrator"
USER_ID = "frontend_user"

# ---------------------------------------------------------------------------
# Estado en memoria (proceso único; reiniciar limpia todo)
# ---------------------------------------------------------------------------
session_service: InMemorySessionService
runner: Runner

# Peticiones en vuelo: request_id → {conversation_id, session_id, message}
pending_requests: dict[str, dict] = {}

# Mapeo conversation_id → session_id para preservar historial entre turnos
conversation_sessions: dict[str, str] = {}


# ---------------------------------------------------------------------------
# Lifespan: inicializa ADK al arrancar
# ---------------------------------------------------------------------------
@asynccontextmanager
async def lifespan(app: FastAPI):
    global session_service, runner
    session_service = InMemorySessionService()
    runner = Runner(
        agent=root_agent,
        app_name=APP_NAME,
        session_service=session_service,
    )
    logger.info("Orchestrator listo → http://%s:%s", os.environ["HOST"], os.environ["PORT"])
    yield


# ---------------------------------------------------------------------------
# App FastAPI
# ---------------------------------------------------------------------------
app = FastAPI(title="Recruiting Orchestrator", version="1.0.0", lifespan=lifespan)

_cors_origins = [o.strip() for o in os.environ["CORS_ALLOWED_ORIGINS"].split(",") if o.strip()]
app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["*"],
)


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------
class ChatRequest(BaseModel):
    conversation_id: str | None = None
    message: str


class ChatInitResponse(BaseModel):
    conversation_id: str
    request_id: str
    stream_url: str


# ---------------------------------------------------------------------------
# Helpers SSE
# ---------------------------------------------------------------------------
def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _sse_step(agent: str, status: str, message: str) -> str:
    data = {"agent": agent, "status": status, "message": message, "timestamp": _now_iso()}
    return f"event: step\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"


def _sse_final(content: str) -> str:
    data = {"role": "assistant", "content": content}
    return f"event: final\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"


def _sse_error(code: str, message: str) -> str:
    data = {"code": code, "message": message}
    return f"event: error\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"


def _extract_step_from_function_call(part) -> tuple[str, str] | None:
    """
    De un FunctionCall del ADK extrae (agent_name, acción legible).
    El orchestrator usa call_external_agent(agent_name=..., payload={action: ...}).
    """
    fc = getattr(part, "function_call", None)
    if not fc:
        return None
    args = dict(fc.args) if fc.args else {}
    agent_name = args.get("agent_name", fc.name)
    payload = args.get("payload", {})
    action = payload.get("action", "procesando") if isinstance(payload, dict) else "procesando"
    return agent_name, action


def _extract_step_from_function_response(part) -> tuple[str, str, str] | None:
    """
    De un FunctionResponse extrae (agent_name, status, mensaje).
    """
    fr = getattr(part, "function_response", None)
    if not fr:
        return None
    response = dict(fr.response) if fr.response else {}
    raw_status = response.get("status", "done")
    step_status = "error" if raw_status == "error" else "done"
    msg = response.get("message", response.get("mensaje", f"{fr.name} completado"))
    if not isinstance(msg, str):
        msg = json.dumps(msg, ensure_ascii=False)[:200]
    return fr.name, step_status, msg


# ---------------------------------------------------------------------------
# POST /chat
# ---------------------------------------------------------------------------
@app.post("/chat", response_model=ChatInitResponse)
async def post_chat(req: ChatRequest) -> ChatInitResponse:
    request_id = str(uuid.uuid4())
    conversation_id = req.conversation_id or str(uuid.uuid4())

    # Reusar o crear session_id para esta conversación
    if conversation_id not in conversation_sessions:
        session_id = f"session_{conversation_id}"
        conversation_sessions[conversation_id] = session_id
    else:
        session_id = conversation_sessions[conversation_id]

    pending_requests[request_id] = {
        "conversation_id": conversation_id,
        "session_id": session_id,
        "message": req.message,
    }

    logger.info("POST /chat → request_id=%s conv=%s", request_id, conversation_id)

    return ChatInitResponse(
        conversation_id=conversation_id,
        request_id=request_id,
        stream_url=f"/chat/stream/{request_id}",
    )


# ---------------------------------------------------------------------------
# GET /chat/stream/{request_id}  — SSE
# ---------------------------------------------------------------------------
@app.get("/chat/stream/{request_id}")
async def stream_chat(request_id: str) -> StreamingResponse:
    req_data = pending_requests.pop(request_id, None)
    if not req_data:
        raise HTTPException(status_code=404, detail="request_id no encontrado o ya consumido")

    async def generate() -> AsyncGenerator[str, None]:
        session_id = req_data["session_id"]
        message = req_data["message"]

        # Crear sesión (ignorar error si ya existe para conversaciones multi-turno)
        try:
            await session_service.create_session(
                app_name=APP_NAME, user_id=USER_ID, session_id=session_id
            )
        except Exception:
            pass

        content = types.Content(role="user", parts=[types.Part(text=message)])

        try:
            async for event in runner.run_async(
                user_id=USER_ID, session_id=session_id, new_message=content
            ):
                if not event.content or not event.content.parts:
                    continue

                for part in event.content.parts:
                    # ── Llamada a sub-agente (tool call) ──────────────────
                    result = _extract_step_from_function_call(part)
                    if result:
                        agent_name, action = result
                        logger.info("Tool call → %s (%s)", agent_name, action)
                        yield _sse_step(agent_name, "running", f"Consultando {agent_name}: {action}")

                    # ── Respuesta de sub-agente (tool response) ───────────
                    result = _extract_step_from_function_response(part)
                    if result:
                        agent_name, step_status, msg = result
                        logger.info("Tool response ← %s (%s): %s", agent_name, step_status, msg[:80])
                        yield _sse_step(agent_name, step_status, msg)

                # ── Respuesta final del orchestrator ──────────────────────
                if event.is_final_response():
                    text = next(
                        (p.text for p in event.content.parts if getattr(p, "text", None)),
                        None,
                    )
                    if text:
                        logger.info("Respuesta final (%d chars)", len(text))
                        yield _sse_final(text)

        except asyncio.CancelledError:
            logger.info("Stream cancelado por el cliente (request_id=%s)", request_id)
        except Exception as exc:
            logger.error("Error en stream: %s", exc, exc_info=True)
            yield _sse_error("ORCHESTRATOR_ERROR", str(exc))

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
            "Connection": "keep-alive",
        },
    )


# ---------------------------------------------------------------------------
# Health
# ---------------------------------------------------------------------------
@app.get("/health")
def health() -> dict:
    return {"status": "ok", "agent": APP_NAME, "pending_requests": len(pending_requests)}


# ---------------------------------------------------------------------------
if __name__ == "__main__":
    uvicorn.run(
        app,
        host=os.environ["HOST"],
        port=int(os.environ["PORT"]),
        log_level=os.environ["LOG_LEVEL"],
    )
