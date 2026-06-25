"""
Configuración del agente busquedas_internas.
Carga variables de entorno desde .env usando pydantic-settings.
Usar `get_settings()` en lugar de instanciar Settings directamente.

Nota: pydantic-settings carga los valores en sus atributos pero NO los escribe
en os.environ. Para que LiteLLM encuentre la API key de Anthropic en el entorno,
cada agent.py llama a `load_dotenv()` explícitamente al inicio del módulo.

Todos los valores se leen del .env. No hay defaults hardcodeados — si una
variable falta, Settings() falla al instanciarse (fail-fast).
"""
from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    CLAUDE_API_KEY: str = Field(description="API Key de Anthropic (Claude)")
    CLAUDE_MODEL: str = Field(description="Modelo Claude a usar (formato LiteLLM, ej. claude-sonnet-4-6)")

    # ── Integración con el MCP de RAGaaS (búsqueda RAG sobre Qdrant) ───────────
    # El agente consume la tool `search` del servidor MCP de la carpeta MCP/.
    # Tienen default para no romper .env existentes; ajustá lo que haga falta.
    RAGAAS_MCP_URL: str = Field(
        default="http://127.0.0.1:8006/mcp",
        description="URL del servidor MCP de RAGaaS (transporte HTTP streamable).",
    )
    RAGAAS_COLLECTION: str = Field(
        default="CVs",
        description="Colección de Qdrant donde están indexados los CVs de candidatos.",
    )
    RAGAAS_MIN_SCORE: float = Field(
        default=0.0,
        description="Score mínimo de similitud [0.0–1.0] para los chunks del MCP.",
    )
    RAGAAS_CHUNKS_PER_CANDIDATE: int = Field(
        default=5,
        description="Chunks pedidos al MCP por candidato (cada CV puede partirse en varios).",
    )

    DEFAULT_TOP_N: int = Field(
        description="Cantidad de candidatos a devolver cuando la JD no especifica una",
    )
    MAX_TOP_N: int = Field(
        description="Tope defensivo de candidatos para no exceder el contexto del LLM",
    )
    MAX_CHARS_POR_CV: int = Field(
        description="Truncado por CV antes de enviarlo al LLM",
    )

    HOST: str = Field(description="Host donde escucha el server FastAPI")
    PORT: int = Field(description="Puerto donde escucha el server FastAPI")
    LOG_LEVEL: str = Field(description="Nivel de log de uvicorn")

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8", "extra": "ignore"}


@lru_cache()
def get_settings() -> Settings:
    """Retorna la instancia cacheada de configuración. Thread-safe."""
    return Settings()
