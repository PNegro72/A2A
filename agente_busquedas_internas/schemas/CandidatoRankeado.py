from schemas.Candidato import Candidato
from pydantic import BaseModel, Field
from typing import List

class CandidatoRankeado(BaseModel):
    """Candidato con score y justificación generados por el LLM."""

    candidato: Candidato
    score: float = Field(
        ge=0.0, le=1.0, description="Score de compatibilidad entre 0.0 y 1.0"
    )
    justificacion: str = Field(
        description="Justificación del score generada por el LLM"
    )
    habilidades_match: List[str] = Field(
        description="Skills del candidato que coinciden con la JD"
    )
    habilidades_faltantes: List[str] = Field(
        description="Skills requeridas en la JD que el candidato no tiene"
    )
