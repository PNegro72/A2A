from pydantic import BaseModel
from typing import List

class Cvs_data(BaseModel):
    id: str
    nombre: str
    texto_cv: str
    embedding : list[float] = []
    score_embedding : float = 0.0