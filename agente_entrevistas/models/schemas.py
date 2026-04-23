"""
Modelos de datos compartidos por todas las herramientas del agente.
Pydantic v2 para validación estricta de entradas/salidas.
"""

from __future__ import annotations
from typing import Optional
from pydantic import BaseModel, Field


# ── Input del orquestador ─────────────────────────────────────────────────────

class EntrevistaInput(BaseModel):
    """Lo que recibe el agente desde el orquestador."""
    candidato_id: str = Field(..., description="UUID del candidato en Supabase")
    proceso_id: str = Field(..., description="UUID del proceso de selección")
    jd_texto: Optional[str] = Field(
        None,
        description="Texto del Job Description. Si viene None, el agente lo busca en Supabase."
    )


# ── Perfil del candidato ──────────────────────────────────────────────────────

class ExperienciaLaboral(BaseModel):
    empresa: str
    cargo: str
    desde: Optional[str] = None
    hasta: Optional[str] = None
    descripcion: Optional[str] = None


class Candidato(BaseModel):
    candidato_id: str
    nombre: str
    email: Optional[str] = None
    linkedin_url: Optional[str] = None
    github_username: Optional[str] = None
    skills: list[str] = []
    experiencia: list[ExperienciaLaboral] = []
    cv_texto: Optional[str] = Field(None, description="Texto completo del CV parseado")
    jd_texto: Optional[str] = Field(None, description="JD del proceso asociado")


# ── Preguntas generadas ───────────────────────────────────────────────────────

class Pregunta(BaseModel):
    categoria: str   # "técnica" | "conductual" | "cultura" | "presión"
    pregunta: str
    objetivo: str
    nivel: str       # "junior" | "semi" | "senior"
    tiempo_estimado_min: int = 3


class PreguntasOutput(BaseModel):
    total: int
    preguntas: list[Pregunta]
    duracion_estimada_min: int


# ── Output final ──────────────────────────────────────────────────────────────

class KitEntrevistaOutput(BaseModel):
    candidato_nombre: str
    proceso_id: str
    kit_path_docx: str
    kit_path_pdf: Optional[str] = None
    preguntas_total: int
    guardado_en_supabase: bool
