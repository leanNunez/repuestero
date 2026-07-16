from decimal import Decimal

from pydantic import BaseModel, ConfigDict


class ClienteLeer(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    codigo: str
    denominacion: str
    cuit: str | None
    cond_fiscal: str
    limite_cta_cte: Decimal
    telefono: str | None
    email: str | None
    direccion: str | None
    activo: bool
