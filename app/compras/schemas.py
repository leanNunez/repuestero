"""Contratos de compras.

`*Crear` = lo que el operador manda (input hostil, se valida como cualquier POST).
`*Leer` = lo que se devuelve. `CompraResponse` es el acuse del alta.

El `costo_unitario` lo pone el operador (es NETO, sin IVA): la compra lo toma tal cual, le calcula
el IVA por renglón, y pisa con él el costo del artículo (repriceando las listas de venta).
"""

from datetime import date
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

_MAX_RENGLONES = 200


class RenglonCompraCrear(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    articulo_codigo: str = Field(min_length=1, max_length=40)
    cantidad: Decimal = Field(gt=0)
    costo_unitario: Decimal = Field(ge=0)  # neto, sin IVA
    #: Si no se manda, se usa la alícuota del artículo.
    alicuota_iva: Decimal | None = Field(default=None, ge=0, le=100)


class CompraCrear(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    proveedor_codigo: str = Field(min_length=1, max_length=20)
    #: A qué depósito entra la mercadería. Sin default: que el stock entre a un lugar por omisión
    #: es como se pierde el control del inventario.
    deposito_codigo: str = Field(min_length=1, max_length=20)
    #: El número de la factura/remito del proveedor. Identifica la compra (no hay correlativo propio).
    numero_comprobante: str = Field(min_length=1, max_length=40)
    condicion: Literal["contado", "cta_cte"] = "contado"
    renglones: list[RenglonCompraCrear] = Field(min_length=1, max_length=_MAX_RENGLONES)


class CompraItemLeer(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    articulo_id: int
    cantidad: Decimal
    costo_unitario: Decimal
    alicuota_iva: Decimal
    importe_iva: Decimal
    total_renglon: Decimal


class CompraLeer(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    proveedor_id: int
    numero_comprobante: str
    fecha: date
    condicion: str
    neto: Decimal
    iva: Decimal
    total: Decimal


class CompraDetalle(CompraLeer):
    items: list[CompraItemLeer] = Field(default_factory=list)


class CompraPagina(BaseModel):
    items: list[CompraLeer]
    total: int


class CompraResponse(BaseModel):
    compra_id: int
    proveedor_id: int
    numero_comprobante: str
    total: Decimal
    movimientos: int = 0


# --------------------------------------------------------------------------- cuenta corriente


class PagoProveedorCrear(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    proveedor_codigo: str = Field(min_length=1, max_length=20)
    monto: Decimal = Field(gt=0)


class PagoProveedorResponse(BaseModel):
    movimiento_id: int
    proveedor_id: int
    #: Saldo del proveedor DESPUÉS de imputar el pago (positivo = le debemos).
    saldo: Decimal


class SaldoProveedorLeer(BaseModel):
    proveedor_id: int
    saldo: Decimal
