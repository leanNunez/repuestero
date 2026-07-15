from typing import Any

from pydantic import BaseModel, Field


class ConsultaRequest(BaseModel):
    # max_length en el boundary: nunca se confía en el tamaño de la entrada del usuario.
    message: str = Field(min_length=1, max_length=500)


class ConsultaResponse(BaseModel):
    answer: str
    sql: str | None = None
    filas: list[dict[str, Any]] = []
    #: True si la consulta se bloqueó por sospecha de prompt injection.
    blocked: bool = False
