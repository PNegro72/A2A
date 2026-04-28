from pydantic import BaseModel, Field
from typing import List, Optional

class JobDescriptionEstructurada(BaseModel):
    """JD parseada y estructurada, lista para ser consumida por otros agentes."""

    role_title: str = Field(description="Título del puesto")
    role_description: str = Field(
        description="Descripción del rol y sus responsabilidades principales"
    )
    management_level: str = Field(description=("Nivel de management requerido."))
    skills: List[str] = Field(
        description="Lista de habilidades técnicas y blandas requeridas"
    )
    cantidad_candidatos: Optional[int] = Field(
        default=None,
        description=(
            "Cantidad de candidatos que el usuario pidió ver explícitamente "
            "(ej.: 'dame 1 candidato', 'necesito 3 perfiles'). null si no se "
            "menciona — en ese caso el agente de búsquedas usa su default."
        ),
    )
