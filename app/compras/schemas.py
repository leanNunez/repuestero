"""Contratos de compras.

`*Crear` = lo que el operador manda (input hostil, se valida como cualquier POST).
`*Leer` = lo que se devuelve. `CompraResponse` es el acuse del alta.

El `costo_unitario` lo pone el operador (es NETO, sin IVA): la compra lo toma tal cual, le calcula
el IVA por renglón, y pisa con él el costo del artículo (repriceando las listas de venta).
"""

from datetime import date, datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.core.fechas import validar_fecha_movimiento
from app.core.formas_pago import FORMA_POR_DEFECTO, FormaPagoLiteral

_MAX_RENGLONES = 200
#: Tope de renglones de forma de pago por orden. Ver `ventas.schemas._MAX_FORMAS_PAGO`.
_MAX_FORMAS_PAGO = 20


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


class FormaPagoCrear(BaseModel):
    """Un renglón de "con qué le pagué". Espejo de `ventas.schemas.FormaPagoCrear`."""

    model_config = ConfigDict(str_strip_whitespace=True)

    forma: FormaPagoLiteral
    monto: Decimal = Field(gt=0)


class FormaPagoLeer(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    forma: str
    monto: Decimal


class OrdenPagoLeer(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    proveedor_id: int
    tipo: str
    pto_venta: int
    numero: int
    fecha: date
    total: Decimal
    formas_pago: list[FormaPagoLeer] = Field(default_factory=list)


class PagoProveedorCrear(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    proveedor_codigo: str = Field(min_length=1, max_length=20)
    monto: Decimal = Field(gt=0)
    #: Cuándo SALIÓ la plata. `None` = hoy. Ver `ventas.schemas.CobranzaCrear.fecha`.
    fecha: date | None = None
    #: Punto de venta de la ORDEN DE PAGO, que se numera aparte de todo lo demás.
    pto_venta: int = Field(default=1, ge=1)
    #: Con qué se pagó. Omitirla asume el total en efectivo (ver el validador de abajo).
    formas_pago: list[FormaPagoCrear] | None = Field(default=None, max_length=_MAX_FORMAS_PAGO)

    _valida_fecha = field_validator("fecha")(validar_fecha_movimiento)

    @model_validator(mode="after")
    def _asume_efectivo(self) -> "PagoProveedorCrear":
        """Sin detalle, el pago fue en efectivo por el total.

        Política de mostrador, no del dominio. Ver `ventas.schemas.CobranzaCrear._asume_efectivo`,
        donde está la explicación larga de por qué el default vive en el borde y no en el service.
        """
        if not self.formas_pago:
            self.formas_pago = [FormaPagoCrear(forma=FORMA_POR_DEFECTO, monto=self.monto)]
        return self


class PagoProveedorResponse(BaseModel):
    movimiento_id: int
    proveedor_id: int
    #: Saldo del proveedor DESPUÉS de imputar el pago (positivo = le debemos).
    saldo: Decimal
    #: La orden de pago emitida. Claves NEUTRAS, iguales a las de `CobranzaResponse`: el front usa
    #: UN solo schema para las dos solapas.
    documento_id: int
    documento_tipo: str
    documento_pto_venta: int
    documento_numero: int


class AjusteCrear(BaseModel):
    """Un ajuste de cuenta corriente de proveedor. Espejo de `ventas.schemas.AjusteCrear`.

    El XOR entre los dos modos se valida ACÁ para que un pedido incoherente muera en el 422 sin
    llegar a tocar la base. El service lo vuelve a chequear: es la puerta de entrada real.
    """

    model_config = ConfigDict(str_strip_whitespace=True)

    #: Obligatorio, y respaldado por el CHECK de la 0009.
    motivo: str = Field(min_length=3, max_length=200)
    #: Movimiento a revertir. El importe lo calcula el SERVICE espejando el original.
    revierte_movimiento_id: int | None = Field(default=None, gt=0)
    #: Solo en ajuste manual, y uno solo de los dos. Sube lo que le debemos.
    debe: Decimal | None = Field(default=None, gt=0)
    #: Solo en ajuste manual, y uno solo de los dos. Baja lo que le debemos.
    haber: Decimal | None = Field(default=None, gt=0)
    #: Cuándo corresponde el ajuste. `None` = hoy.
    fecha: date | None = None

    _valida_fecha = field_validator("fecha")(validar_fecha_movimiento)

    @model_validator(mode="after")
    def _un_modo_solo(self) -> "AjusteCrear":
        importes = [m for m in (self.debe, self.haber) if m is not None]

        if self.revierte_movimiento_id is not None:
            if importes:
                raise ValueError(
                    "Una reversa no lleva importe: lo calcula el sistema desde el original."
                )
            return self

        if not importes:
            raise ValueError("Un ajuste manual lleva un importe en Debe o en Haber.")
        if len(importes) == 2:
            raise ValueError("Un ajuste va en Debe o en Haber, no en los dos a la vez.")
        return self


class AnulacionCrear(BaseModel):
    """Anular una orden de pago. Espejo de `ventas.AnulacionCrear`."""

    model_config = ConfigDict(str_strip_whitespace=True)

    motivo: str = Field(min_length=3, max_length=200)


class AjusteResponse(BaseModel):
    movimiento_id: int
    proveedor_id: int
    #: Saldo del proveedor DESPUÉS del ajuste. Mismo shape que `PagoProveedorResponse`: el front
    #: usa UN solo schema para las dos mutaciones de las dos solapas.
    saldo: Decimal


class SaldoProveedorLeer(BaseModel):
    proveedor_id: int
    saldo: Decimal


class CuentaLeer(BaseModel):
    """Una cuenta corriente con su saldo.

    Mismo shape que la de clientes (`app/ventas/schemas.py`) a propósito: el front tiene UN
    schema, UNA tabla y UN hook para las dos solapas. Por eso `nombre` y no `razon_social`.
    """

    id: int
    #: Los pagos se imputan por CÓDIGO, no por id: viaja para que el front pueda postear.
    codigo: str
    nombre: str
    #: Positivo = le debemos al proveedor. Negativo = le pagamos de más o tenemos crédito.
    saldo: Decimal
    #: Existe solo para espejar el shape de clientes: los proveedores no tienen límite de
    #: crédito cargado en el sistema. Siempre None.
    limite: Decimal | None = None


class CuentaPagina(BaseModel):
    items: list[CuentaLeer]
    total: int
    #: Suma de saldos del conjunto FILTRADO, no de la página. Mezcla signos: es el neto a pagar.
    saldo_total: Decimal


class MovimientoLeer(BaseModel):
    id: int
    fecha: date
    tipo: str  # 'compra' | 'pago' | 'ajuste'
    debe: Decimal
    haber: Decimal
    ref_tipo: str | None = None
    ref_id: int | None = None
    #: Por qué se ajustó. Solo lo traen los movimientos de tipo 'ajuste'.
    motivo: str | None = None
    #: Cuándo se REGISTRÓ, contra `fecha`, que es cuándo pasó. Ver el espejo en ventas.
    creado_en: datetime
    #: Si un ajuste posterior ya revirtió este movimiento.
    anulado: bool = False
    #: "¿Puedo apretar Revertir en esta fila?" — ya contempla que un movimiento anulado no se
    #: revierte de nuevo. Viaja calculado para que la regla viva SOLO en el service.
    reversible: bool = False
    #: Saldo DESPUÉS de este movimiento, en orden cronológico. Lo calcula el SQL sobre todo el
    #: ledger: el front solo ve una página y no puede conocer el acumulado de las anteriores.
    saldo_acumulado: Decimal


class MovimientoPagina(BaseModel):
    items: list[MovimientoLeer]
    total: int
    #: Cabecera de la cuenta, para que un deep link pinte nombre y saldo sin depender de que
    #: esa cuenta haya caído en la página del listado.
    cuenta: CuentaLeer
