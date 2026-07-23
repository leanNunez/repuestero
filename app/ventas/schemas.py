"""Contratos de ventas.

`*Crear` = lo que el mostrador manda (input hostil, se valida como cualquier POST).
`*Leer` = lo que se devuelve. `VentaResponse` es el acuse del alta.

El `precio_unitario` lo pone el operador (es NETO, sin IVA): la venta lo toma tal cual viene y
le calcula el IVA por renglón. `GET /ventas/precio-sugerido` propone un precio (el de la lista
del cliente, o Mostrador) para precargar el renglón, pero es solo sugerencia editable.
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


class PrecioSugeridoLeer(BaseModel):
    articulo_codigo: str
    #: Precio neto sugerido, o None si esa lista no tiene precio fijado (el operador lo tipea).
    precio: Decimal | None = None
    #: Código de la lista de la que salió el precio ('MOST', etc.), para mostrar de dónde viene.
    lista_codigo: str | None = None


# --------------------------------------------------------------------------- cuenta corriente


class CobranzaCrear(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    cliente_codigo: str = Field(min_length=1, max_length=20)
    monto: Decimal = Field(gt=0)


class CobranzaResponse(BaseModel):
    movimiento_id: int
    cliente_id: int
    #: Saldo del cliente DESPUÉS de imputar la cobranza (positivo = debe, negativo = a favor).
    saldo: Decimal


class SaldoLeer(BaseModel):
    cliente_id: int
    saldo: Decimal


# --------------------------------------------------------------------------- notas de crédito


class RenglonNotaCreditoCrear(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    articulo_codigo: str = Field(min_length=1, max_length=40)
    #: Cuánto se acredita de este artículo. El precio y el IVA NO se mandan: se copian del
    #: renglón original de la venta (no se puede acreditar a un precio distinto al que se cobró).
    cantidad: Decimal = Field(gt=0)


class NotaCreditoCrear(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    #: Id del comprobante de venta que se corrige.
    comprobante_id: int = Field(gt=0)
    #: Renglones a acreditar (parcial). Si viene None/vacío = anulación TOTAL: se acredita todo
    #: lo que reste de cada renglón de la venta.
    renglones: list[RenglonNotaCreditoCrear] | None = Field(default=None, max_length=_MAX_RENGLONES)


class NotaCreditoItemLeer(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    articulo_id: int
    cantidad: Decimal
    precio_unitario: Decimal
    alicuota_iva: Decimal
    importe_iva: Decimal
    total_renglon: Decimal


class NotaCreditoLeer(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    ref_comprobante_id: int
    cliente_id: int
    tipo: str
    pto_venta: int
    numero: int
    fecha: date
    condicion: str
    neto: Decimal
    iva: Decimal
    total: Decimal


class NotaCreditoDetalle(NotaCreditoLeer):
    items: list[NotaCreditoItemLeer] = Field(default_factory=list)


class NotaCreditoPagina(BaseModel):
    items: list[NotaCreditoLeer]
    total: int


class NotaCreditoResponse(BaseModel):
    nota_credito_id: int
    ref_comprobante_id: int
    tipo: str
    pto_venta: int
    numero: int
    total: Decimal
    movimientos: int = 0


class RenglonAcreditableLeer(BaseModel):
    """Lo que resta acreditar de un renglón de una venta, para precargar el flujo de NC."""

    articulo_id: int
    articulo_codigo: str
    descripcion: str
    precio_unitario: Decimal
    alicuota_iva: Decimal
    cantidad_vendida: Decimal
    cantidad_acreditable: Decimal
