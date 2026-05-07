"""
Configuración del agente job_description.
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
    CLAUDE_MODEL: str = Field(description="Modelo Claude a usar (formato LiteLLM)")

    HOST: str = Field(description="Host donde escucha el server FastAPI")
    PORT: int = Field(description="Puerto donde escucha el server FastAPI")
    LOG_LEVEL: str = Field(description="Nivel de log de uvicorn")

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8", "extra": "ignore"}


@lru_cache()
def get_settings() -> Settings:
    """Retorna la instancia cacheada de configuración. Thread-safe."""
    return Settings()
