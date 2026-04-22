from pydantic import BaseModel
from schemas.cvs_data import Cvs_data

class Busqueda_response(BaseModel):
    exito: bool
    candidatos: list[Cvs_data]
    total: int
    mensaje: str