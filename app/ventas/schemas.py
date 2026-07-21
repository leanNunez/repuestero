"""Contratos de ventas.

`*Crear` = lo que el mostrador manda (input hostil, se valida como cualquier POST).
`*Leer` = lo que se devuelve. `VentaResponse` es el acuse del alta.

El `precio_unitario` lo pone el operador (es NETO, sin IVA). El sistema no lo saca solo de la
lista de precios en este slice: se toma tal cual viene y se le calcula el IVA por renglón.
"""

from datetime import date
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

_MAX_RENGLONES = 200


class RenglonVentaCrear(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    articulo_codigo: str = Field(min_length=1, max_length=40)
    cantidad: Decimal = Field(gt=0)
    precio_unitario: Decimal = Field(ge=0)  # neto, sin IVA
    #: Si no se manda, se usa la alícuota del artículo.
    alicuota_iva: Decimal | None = Field(default=None, ge=0, le=100)


class VentaCrear(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    cliente_codigo: str = Field(min_length=1, max_length=20)
    #: De qué depósito sale la mercadería. Sin default: que el stock salga de un lugar por
    #: omisión es como se pierde el control del inventario.
    deposito_codigo: str = Field(min_length=1, max_length=20)
    tipo: str = Field(default="FAC", min_length=1, max_length=10)
    pto_venta: int = Field(default=1, ge=1)
    condicion: Literal["contado", "cta_cte"] = "contado"
    renglones: list[RenglonVentaCrear] = Field(min_length=1, max_length=_MAX_RENGLONES)


class VentaItemLeer(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    articulo_id: int
    cantidad: Decimal
    precio_unitario: Decimal
    alicuota_iva: Decimal
    importe_iva: Decimal
    total_renglon: Decimal


class VentaLeer(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    cliente_id: int
    tipo: str
    pto_venta: int
    numero: int
    fecha: date
    condicion: str
    neto: Decimal
    iva: Decimal
    total: Decimal


class VentaDetalle(VentaLeer):
    items: list[VentaItemLeer] = Field(default_factory=list)


class VentaPagina(BaseModel):
    items: list[VentaLeer]
    total: int


class VentaResponse(BaseModel):
    venta_id: int
    tipo: str
    pto_venta: int
    numero: int
    total: Decimal
    movimientos: int = 0
    advertencias: list[str] = Field(default_factory=list)
