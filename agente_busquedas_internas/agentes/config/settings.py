"""
Configuración del agente busquedas_internas.
Carga variables de entorno desde .env usando pydantic-settings.
Usar `get_settings()` en lugar de instanciar Settings directamente.

Nota: pydantic-settings carga los valores en sus atributos pero NO los escribe
en os.environ. Para que LiteLLM encuentre OPENAI_API_KEY en el entorno, cada agent.py
llama a `load_dotenv()` explícitamente al inicio del módulo.

Todos los valores se leen del .env. No hay defaults hardcodeados — si una
variable falta, Settings() falla al instanciarse (fail-fast).
"""
from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    OPENAI_API_KEY: str = Field(description="API Key de OpenAI (GPT)")
    OPENAI_MODEL: str = Field(description="Modelo OpenAI a usar (formato LiteLLM)")

    CVS_DIR: Path = Field(description="Directorio con los CVs en formato .pptx")

    EMBEDDING_MODEL: str = Field(
        description="Modelo de sentence-transformers para embeddings de CVs y JDs",
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
