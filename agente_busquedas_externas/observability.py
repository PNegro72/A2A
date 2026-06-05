"""
Observabilidad para agentes Google ADK via Langfuse + OpenInference.

Llamar a init_observability(service_name) ANTES de cualquier import de google.adk.
"""
import base64
import logging
import os

from dotenv import load_dotenv

logger = logging.getLogger(__name__)


def init_observability(service_name: str) -> bool:
    """
    Conecta el agente a Langfuse vía OTel + OpenInference ADK instrumentation.

    Comportamiento:
    - LANGFUSE_PUBLIC_KEY / LANGFUSE_SECRET_KEY ausentes → advertencia, retorna False.
    - Claves presentes pero inválidas → RuntimeError (fail-fast).
    - Todo OK → instrumenta ADK, loguea URL de traces, retorna True.
    """
    load_dotenv()

    public_key = os.getenv("LANGFUSE_PUBLIC_KEY", "")
    secret_key = os.getenv("LANGFUSE_SECRET_KEY", "")
    host = os.getenv("LANGFUSE_HOST", "https://cloud.langfuse.com")

    if not public_key or not secret_key:
        logger.warning(
            "[observability] Langfuse NO configurado — LANGFUSE_PUBLIC_KEY o "
            "LANGFUSE_SECRET_KEY ausentes. %s correrá sin observabilidad.",
            service_name,
        )
        return False

    try:
        from langfuse import Langfuse

        lf = Langfuse(public_key=public_key, secret_key=secret_key, host=host)
        if not lf.auth_check():
            raise RuntimeError(
                f"[observability] Credenciales Langfuse inválidas para '{service_name}'. "
                "Verificá LANGFUSE_PUBLIC_KEY y LANGFUSE_SECRET_KEY en el .env."
            )
    except RuntimeError:
        raise
    except Exception as exc:
        raise RuntimeError(
            f"[observability] Error verificando credenciales Langfuse: {exc}"
        ) from exc

    try:
        from opentelemetry import trace
        from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
        from opentelemetry.sdk.resources import Resource
        from opentelemetry.sdk.trace import TracerProvider
        from opentelemetry.sdk.trace.export import BatchSpanProcessor

        auth_token = base64.b64encode(f"{public_key}:{secret_key}".encode()).decode()
        otlp_endpoint = f"{host.rstrip('/')}/api/public/otel/v1/traces"

        exporter = OTLPSpanExporter(
            endpoint=otlp_endpoint,
            headers={"Authorization": f"Basic {auth_token}"},
        )
        provider = TracerProvider(resource=Resource.create({"service.name": service_name}))
        provider.add_span_processor(BatchSpanProcessor(exporter))
        trace.set_tracer_provider(provider)

    except Exception as exc:
        raise RuntimeError(
            f"[observability] Error configurando OTel TracerProvider: {exc}"
        ) from exc

    try:
        from openinference.instrumentation.google_adk import GoogleADKInstrumentor

        GoogleADKInstrumentor().instrument()
    except Exception as exc:
        raise RuntimeError(
            f"[observability] Error instrumentando Google ADK: {exc}"
        ) from exc

    traces_url = f"{host}/traces"
    logger.info(
        "[observability] Langfuse conectado — servicio=%s | %s", service_name, traces_url
    )
    print(f"[observability] Langfuse conectado → {traces_url}  (servicio: {service_name})")
    return True
