from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field


class ArticuloCrear(BaseModel):
    codigo: str = Field(max_length=40)
    detalle: str = Field(max_length=200)
    costo: Decimal = Decimal("0")
    costo_dolar: Decimal | None = None
    alicuota_iva: Decimal = Decimal("21.00")
    punto_pedido: Decimal = Decimal("0")
    codigo_barra: str | None = None
    marca: str | None = None
    rubro: str | None = None


class ArticuloLeer(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    codigo: str
    detalle: str
    costo: Decimal
    alicuota_iva: Decimal
    punto_pedido: Decimal
    marca: str | None
    rubro: str | None
    activo: bool


class ListaPrecioCrear(BaseModel):
    codigo: str = Field(max_length=30)
    nombre: str = Field(max_length=80)


class PrecioCrear(BaseModel):
    articulo_codigo: str
    lista_codigo: str
    precio: Decimal
    margen: Decimal | None = None
