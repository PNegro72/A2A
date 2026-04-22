"""
Configuración del agente job_description.
Carga variables de entorno desde .env usando pydantic-settings.
Usar `get_settings()` en lugar de instanciar Settings directamente.

Nota: pydantic-settings carga los valores en sus atributos pero NO los escribe
en os.environ. Para que ADK encuentre ANTHROPIC_API_KEY en el entorno, cada agent.py
llama a `load_dotenv()` explícitamente al inicio del módulo.
"""
from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    OPENAI_API_KEY: str = Field(default="", description="API Key de OpenAI (GPT)")
    OPENAI_MODEL: str = Field(default="gpt-4", description="Modelo OpenAI a usar (formato LiteLLM)")

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}


@lru_cache()
def get_settings() -> Settings:
    """Retorna la instancia cacheada de configuración. Thread-safe."""
    return Settings()
