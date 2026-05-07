from pydantic import BaseModel, Field
from typing import List, Optional, Literal


class JobDescriptionRedactada(BaseModel):
    """
    Job Description generada por el agente a partir de una request corta del usuario.
    A diferencia de JobDescriptionEstructurada (que parsea texto existente), este
    schema describe una JD redactada por el LLM con todas sus secciones.
    """

    idioma: Literal["es", "en"] = Field(
        description=(
            "Idioma detectado de la request. 'es' si el usuario escribió en español, "
            "'en' si lo hizo en inglés. La JD completa se genera en este mismo idioma."
        )
    )

    titulo: str = Field(description="Título del puesto, formal y descriptivo.")

    resumen: str = Field(
        description=(
            "Resumen ejecutivo del rol en 1-2 oraciones. Va arriba de la JD para "
            "que el candidato entienda rápido de qué se trata."
        )
    )

    responsabilidades: List[str] = Field(
        description=(
            "Lista de responsabilidades principales del rol (4-7 ítems). "
            "Cada ítem en infinitivo y orientado a impacto."
        )
    )

    requisitos_obligatorios: List[str] = Field(
        description=(
            "Skills, experiencia y conocimientos no negociables (3-7 ítems). "
            "Incluye años de experiencia si la request lo sugiere."
        )
    )

    requisitos_deseables: List[str] = Field(
        default_factory=list,
        description=(
            "Skills o experiencia 'nice to have' (0-5 ítems). Lista vacía si "
            "la request no da pistas suficientes."
        ),
    )

    seniority: Literal["Junior", "Semi-Senior", "Senior", "Lead"] = Field(
        description=(
            "Nivel de experiencia del rol. Inferilo de la request; si no hay "
            "señales claras, usá 'Semi-Senior'."
        )
    )

    management_level: Literal[
        "Individual Contributor",
        "Team Lead",
        "Manager",
        "Senior Manager",
        "Director",
        "Vice President",
    ] = Field(
        description=(
            "Nivel de gestión de personas. 'Individual Contributor' por default si "
            "la request no menciona liderazgo de personas."
        )
    )

    modalidad: Optional[Literal["Presencial", "Híbrido", "Remoto"]] = Field(
        default=None,
        description=(
            "Modalidad de trabajo si la request la menciona. null si no está "
            "especificada."
        ),
    )

    cantidad_candidatos: Optional[int] = Field(
        default=None,
        description=(
            "Cantidad de candidatos que el usuario pidió ver explícitamente "
            "(ej.: 'necesito 3 devs Python'). null si no se menciona — en ese "
            "caso el agente de búsquedas usa su default."
        ),
    )

    texto_completo: str = Field(
        description=(
            "JD completa en formato Markdown, lista para copiar/pegar. Debe "
            "incluir todas las secciones (título, resumen, responsabilidades, "
            "requisitos obligatorios, requisitos deseables si los hay, "
            "modalidad si está) en el idioma detectado."
        )
    )