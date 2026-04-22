from pydantic import BaseModel, Field
from typing import List, Optional
from datetime import datetime
from schemas.CandidatoRankeado import CandidatoRankeado
from schemas.JobDescriptionEstructurada import JobDescriptionEstructurada

class ResultadoRanking(BaseModel):
    """Resultado completo del proceso de búsqueda y ranking de candidatos."""

    job_description: JobDescriptionEstructurada
    candidatos_rankeados: List[CandidatoRankeado] = Field(
        description="Lista de candidatos ordenada de mayor a menor score"
    )
    total_candidatos_evaluados: int
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    estado: str = Field(
        description="Estado del proceso: 'exito', 'sin_resultados', 'error'"
    )
    mensaje: Optional[str] = Field(
        default=None, description="Mensaje adicional o de error"
    )
