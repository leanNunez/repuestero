"""Contratos de ventas.

`*Crear` = lo que el mostrador manda (input hostil, se valida como cualquier POST).
`*Leer` = lo que se devuelve. `VentaResponse` es el acuse del alta.

El `precio_unitario` lo pone el operador (es NETO, sin IVA): la venta lo toma tal cual viene y
le calcula el IVA por renglón. `GET /ventas/precio-sugerido` propone un precio (el de la lista
del cliente, o Mostrador) para precargar el renglón, pero es solo sugerencia editable.
"""

from datetime import date, datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.core.fechas import validar_fecha_movimiento
from app.core.formas_pago import FORMA_POR_DEFECTO, FormaPagoLiteral

_MAX_RENGLONES = 200
#: Tope de renglones de forma de pago por recibo. Un cobro se cancela con dos o tres medios, no
#: con veinte: el límite es contra el payload hostil, no contra el mostrador.
_MAX_FORMAS_PAGO = 20


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


class FormaPagoCrear(BaseModel):
    """Un renglón de "con qué me pagaron". El `Literal` rechaza una forma inventada acá, en el
    borde, con un 422 legible — antes de que llegue al CHECK de la base."""

    model_config = ConfigDict(str_strip_whitespace=True)

    forma: FormaPagoLiteral
    monto: Decimal = Field(gt=0)


class FormaPagoLeer(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    forma: str
    monto: Decimal


class ReciboLeer(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    cliente_id: int
    tipo: str
    pto_venta: int
    numero: int
    fecha: date
    total: Decimal
    formas_pago: list[FormaPagoLeer] = Field(default_factory=list)


class CobranzaCrear(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    cliente_codigo: str = Field(min_length=1, max_length=20)
    monto: Decimal = Field(gt=0)
    #: Cuándo ENTRÓ la plata. `None` = hoy. La plata del viernes cargada el lunes va con la del
    #: viernes; `creado_en` guarda igual el momento del alta, así que el retroactivo es auditable.
    fecha: date | None = None
    #: Punto de venta del RECIBO, que se numera aparte de las facturas. Mismo default que
    #: `VentaCrear`: un mostrador solo no tiene que elegir nada.
    pto_venta: int = Field(default=1, ge=1)
    #: Con qué se cobró. Omitirla asume el total en efectivo (ver el validador de abajo).
    formas_pago: list[FormaPagoCrear] | None = Field(default=None, max_length=_MAX_FORMAS_PAGO)

    _valida_fecha = field_validator("fecha")(validar_fecha_movimiento)

    @model_validator(mode="after")
    def _asume_efectivo(self) -> "CobranzaCrear":
        """Sin detalle, el cobro fue en efectivo por el total.

        Es política de MOSTRADOR y por eso vive acá y no en el service, que exige el dato siempre
        (mismo criterio que la ventana de 90 días de `validar_fecha_movimiento`). Dos razones para
        que el default esté en el borde: mantiene válido el payload que el front ya manda, y deja
        al importador de Paradox —que tiene el detalle real— fuera de este atajo.
        """
        if not self.formas_pago:
            self.formas_pago = [FormaPagoCrear(forma=FORMA_POR_DEFECTO, monto=self.monto)]
        return self


class CobranzaResponse(BaseModel):
    movimiento_id: int
    cliente_id: int
    #: Saldo del cliente DESPUÉS de imputar la cobranza (positivo = debe, negativo = a favor).
    saldo: Decimal
    #: El recibo emitido. Claves NEUTRAS (`documento_*` y no `recibo_*`) porque el front usa UN
    #: solo schema para cobranza y pago a proveedor, donde el documento es una orden de pago.
    documento_id: int
    documento_tipo: str
    documento_pto_venta: int
    documento_numero: int


class AjusteCrear(BaseModel):
    """Un ajuste de cuenta corriente: reversa de un movimiento, o corrección a mano.

    El XOR entre los dos modos se valida ACÁ para que un pedido incoherente muera en el 422 sin
    llegar a tocar la base. El service lo vuelve a chequear igual: es la puerta de entrada real y
    no puede confiar en que alguien haya pasado por este schema.
    """

    model_config = ConfigDict(str_strip_whitespace=True)

    #: Obligatorio. Un ajuste sin motivo es una fila que en seis meses nadie puede explicar; el
    #: CHECK de la 0009 lo respalda en la base.
    motivo: str = Field(min_length=3, max_length=200)
    #: Movimiento a revertir. Si viene, el importe lo calcula el SERVICE espejando el original: no
    #: se manda desde afuera, así no se puede errar tipeando el monto que se está corrigiendo.
    revierte_movimiento_id: int | None = Field(default=None, gt=0)
    #: Solo en ajuste manual, y uno solo de los dos. Sube la deuda del cliente.
    debe: Decimal | None = Field(default=None, gt=0)
    #: Solo en ajuste manual, y uno solo de los dos. Baja la deuda del cliente.
    haber: Decimal | None = Field(default=None, gt=0)
    #: Cuándo corresponde el ajuste. `None` = hoy. Un saldo inicial de migración no es de hoy.
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
    """Anular un recibo. Solo lleva el motivo: el importe lo calcula el sistema desde el documento.

    Es lo que reemplazó a "revertir la cobranza" desde el extracto, porque un recibo dejó de tener
    un solo efecto. Ver `service.anular_recibo`.
    """

    model_config = ConfigDict(str_strip_whitespace=True)

    #: Obligatorio, igual que en un ajuste: una anulación sin motivo es una fila que en seis meses
    #: nadie puede explicar.
    motivo: str = Field(min_length=3, max_length=200)


class AjusteResponse(BaseModel):
    movimiento_id: int
    cliente_id: int
    #: Saldo del cliente DESPUÉS del ajuste. Mismo shape que `CobranzaResponse` a propósito: el
    #: front usa UN solo schema para las dos mutaciones.
    saldo: Decimal


class SaldoLeer(BaseModel):
    cliente_id: int
    saldo: Decimal


class CuentaLeer(BaseModel):
    """Una cuenta corriente con su saldo.

    Mismo shape que la de proveedores (`app/compras/schemas.py`) a propósito: el front tiene UN
    schema, UNA tabla y UN hook para las dos solapas. Por eso `nombre` y no `denominacion`.
    """

    id: int
    #: Las cobranzas se imputan por CÓDIGO, no por id: viaja para que el front pueda postear.
    codigo: str
    nombre: str
    #: Positivo = el cliente debe. Negativo = tiene saldo a favor (nota de crédito o sobrepago).
    saldo: Decimal
    #: `limite_cta_cte`. Hoy es informativo: NADIE lo hace cumplir todavía.
    limite: Decimal | None = None


class CuentaPagina(BaseModel):
    items: list[CuentaLeer]
    total: int
    #: Suma de saldos del conjunto FILTRADO, no de la página. Mezcla signos: es el neto a cobrar,
    #: no el total adeudado. Va acá y no en un endpoint aparte porque describe el mismo conjunto
    #: que `total`, y dos requests separados podrían discrepar si entra una cobranza en el medio.
    saldo_total: Decimal


class MovimientoLeer(BaseModel):
    id: int
    fecha: date
    tipo: str  # 'venta' | 'cobranza' | 'nota_credito' | 'ajuste'
    debe: Decimal
    haber: Decimal
    ref_tipo: str | None = None
    ref_id: int | None = None
    #: Por qué se ajustó. Solo lo traen los movimientos de tipo 'ajuste'.
    motivo: str | None = None
    #: Cuándo se REGISTRÓ, contra `fecha`, que es cuándo pasó. Con movimientos retroactivos las dos
    #: dejan de coincidir, y mostrarlas es lo que hace auditable al retroactivo.
    creado_en: datetime
    #: Si un ajuste posterior ya revirtió este movimiento. Sin esto el extracto muestra el haber y
    #: su contra-debe sin ninguna pista de que se cancelan entre sí.
    anulado: bool = False
    #: La respuesta a "¿puedo apretar Revertir en esta fila?" — NO una propiedad del tipo: ya
    #: contempla que un movimiento anulado no se revierte de nuevo. Viaja calculado para que la
    #: regla de qué se puede revertir viva SOLO en `service.MOVIMIENTOS_REVERSIBLES`.
    reversible: bool = False
    #: Saldo DESPUÉS de este movimiento, en orden cronológico. Lo calcula el SQL sobre todo el
    #: ledger: el front solo ve una página y no puede conocer el acumulado de las anteriores.
    saldo_acumulado: Decimal


class MovimientoPagina(BaseModel):
    items: list[MovimientoLeer]
    total: int
    #: Cabecera de la cuenta. Va en la respuesta para que un deep link (?sel=12) pinte nombre y
    #: saldo sin depender de que esa cuenta haya caído en la página del listado.
    cuenta: CuentaLeer


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
