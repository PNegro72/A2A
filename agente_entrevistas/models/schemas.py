"""
Modelos de datos compartidos por todas las herramientas del agente.
Pydantic v2 para validación estricta de entradas/salidas.
"""

from __future__ import annotations
from typing import Optional
from pydantic import BaseModel, Field


class EntrevistaInput(BaseModel):
    candidato_id: str = Field(..., description="UUID del candidato")
    proceso_id:   str = Field(..., description="UUID del proceso de selección")
    jd_texto: Optional[str] = Field(None, description="Job Description (opcional)")


class ExperienciaLaboral(BaseModel):
    empresa:     str
    cargo:       str
    desde:       Optional[str] = None
    hasta:       Optional[str] = None
    descripcion: Optional[str] = None


class Candidato(BaseModel):
    candidato_id:     str
    nombre:           str
    email:            Optional[str] = None
    linkedin_url:     Optional[str] = None
    github_username:  Optional[str] = None
    skills:           list[str] = []
    experiencia:      list[ExperienciaLaboral] = []
    cv_texto:         Optional[str] = None
    jd_texto:         Optional[str] = None


class Pregunta(BaseModel):
    categoria:           str
    pregunta:            str
    objetivo:            str
    nivel:               str
    tiempo_estimado_min: int = 3


class PreguntasOutput(BaseModel):
    total:                  int
    preguntas:              list[Pregunta]
    duracion_estimada_min:  int


class KitEntrevistaOutput(BaseModel):
    candidato_nombre:    str
    proceso_id:          str
    kit_path_docx:       str
    kit_path_pdf:        Optional[str] = None
    preguntas_total:     int
    guardado_en_supabase: bool
