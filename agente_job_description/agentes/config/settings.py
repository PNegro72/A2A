"""
Configuración del agente job_description.
Carga variables de entorno desde .env usando pydantic-settings.
Usar `get_settings()` en lugar de instanciar Settings directamente.

Nota: pydantic-settings carga los valores en sus atributos pero NO los escribe
en os.environ. Para que LiteLLM encuentre OPENAI_API_KEY en el entorno, cada agent.py
llama a `load_dotenv()` explícitamente al inicio del módulo.
"""
from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    OPENAI_API_KEY: str = Field(default="", description="API Key de OpenAI (GPT)")
    OPENAI_MODEL: str = Field(
        default="gpt-4o-mini", description="Modelo OpenAI a usar (formato LiteLLM)"
    )

    HOST: str = Field(default="127.0.0.1", description="Host donde escucha el server FastAPI")
    PORT: int = Field(default=8001, description="Puerto donde escucha el server FastAPI")
    LOG_LEVEL: str = Field(default="info", description="Nivel de log de uvicorn")

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8", "extra": "ignore"}


@lru_cache()
def get_settings() -> Settings:
    """Retorna la instancia cacheada de configuración. Thread-safe."""
    return Settings()
