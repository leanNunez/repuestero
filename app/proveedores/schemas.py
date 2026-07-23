from pydantic import BaseModel, ConfigDict


class ProveedorLeer(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    codigo: str
    razon_social: str
    cuit: str | None
    telefono: str | None
    email: str | None
    activo: bool
