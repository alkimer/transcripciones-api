from pydantic import BaseModel
from datetime import datetime

class Transcripcion(BaseModel):
    fuente: str
    timestamp_inicio: datetime
    timestamp_fin: datetime
    texto: str
