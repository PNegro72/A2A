from pydantic import BaseModel, Field
from typing import List, Optional


class Candidato(BaseModel):
    """Perfil de un candidato interno obtenido del ATS (Workday)."""

    id: str = Field(description="ID único del empleado en Workday")
    nombre: str
    apellido: str
    email: Optional[str] = None
    cargo_actual: Optional[str] = None
    departamento: Optional[str] = None
    skills: List[str]
    experiencia_años: int
    nivel_management: str
    pais: Optional[str] = None
    disponibilidad: str = Field(default="a confirmar")
