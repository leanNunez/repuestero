from datetime import date, datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.core.conceptos_caja import ConceptoManualLiteral
from app.core.fechas import validar_fecha_movimiento
from app.core.formas_pago import FormaPagoLiteral

#: Los estados del papel, como tipo, para que `?estado=extraviado` muera en Pydantic con un 422
#: legible en vez de devolver una lista vacía sin explicar por qué. Mismo criterio que
#: `FormaPagoLiteral`; el candado contra el CHECK de la 0011 es un test.
EstadoChequeLiteral = Literal[
    "en_cartera", "depositado", "cobrado", "rechazado", "entregado", "anulado"
]


class MovimientoCajaCrear(BaseModel):
    """Alta MANUAL de un movimiento de caja.

    `concepto` es `ConceptoManualLiteral`, no el catálogo completo: un payload con
    `concepto: "cobranza"` muere en Pydantic con un 422 legible, sin llegar al service. Es la
    misma reja del invariante ("si hay documento, caja no se toca a mano") puesta en el borde,
    donde el error es más barato. El service la repite igual — el borde HTTP no es el único
    camino a la caja (está el importador).

    NO se pide el signo: lo determina el concepto. Ver `service.registrar_movimiento`.
    """

    model_config = ConfigDict(str_strip_whitespace=True)

    concepto: ConceptoManualLiteral
    forma: FormaPagoLiteral
    monto: Decimal = Field(gt=0)
    detalle: str | None = Field(default=None, max_length=200)
    #: Cuándo se movió la plata. `None` = hoy.
    fecha: date | None = None

    _valida_fecha = field_validator("fecha")(validar_fecha_movimiento)


class MovimientoCajaLeer(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    fecha: date
    concepto: str
    forma: str
    ingreso: Decimal
    egreso: Decimal
    detalle: str | None
    #: NULL = lo cargó una persona. Cargados = lo emitió un documento.
    ref_tipo: str | None
    ref_id: int | None
    creado_en: datetime
    #: Cuánto había de ESTA forma después de este movimiento. Lo calcula el SQL, nunca el front.
    saldo_acumulado: Decimal


class MovimientoCajaPagina(BaseModel):
    items: list[MovimientoCajaLeer]
    total: int


class SaldoCajaLeer(BaseModel):
    """El saldo discriminado por forma, más el efectivo aparte por ser LA pregunta de caja.

    `efectivo` es redundante con `por_forma["efectivo"]` a propósito: es el número que la pantalla
    muestra grande, y hacer que el front lo saque de un diccionario invita a que cada consumidor
    repita la clave mágica.
    """

    efectivo: Decimal
    por_forma: dict[str, Decimal]


class MovimientoCajaResponse(BaseModel):
    movimiento_id: int
    concepto: str
    forma: str
    #: El saldo de la forma que se acaba de mover, ya recalculado.
    saldo: Decimal
    #: Lo que hay que mirar, sin que nada se haya bloqueado. Hoy: el saldo quedó en negativo, que es
    #: físicamente imposible. Mismo nombre de campo que `VentaResponse.advertencias` y que
    #: `ingesta_visual`, para que el front lea la misma clave en todos lados.
    advertencias: list[str] = Field(default_factory=list)


# ================================================================================ cartera


class ChequeLeer(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    #: 'recibido' (me lo dio un cliente) | 'emitido' (lo firmé yo)
    origen: str
    importe: Decimal
    estado: str
    #: NULL mientras nadie los haya completado desde la pantalla de cartera: un renglón de forma de
    #: pago solo trae forma y monto.
    banco: str | None
    numero: str | None
    fecha_emision: date | None
    fecha_cobro: date | None
    conciliado: bool
    fecha_conciliacion: date | None
    #: De qué documento salió: 'recibo' u 'orden_pago'.
    ref_tipo: str | None
    ref_id: int | None
    creado_en: datetime


class ChequePagina(BaseModel):
    items: list[ChequeLeer]
    total: int
    #: Cuánto valen los cheques todavía en cartera. Es del TOTAL de la org, no de la página: una
    #: suma que dependiera de la paginación no serviría para arquear.
    valor_en_cartera: Decimal


class ChequeTransicionBody(BaseModel):
    """Cuerpo opcional de una transición: solo la fecha en que se movió la plata.

    `depositar` la ignora (no mueve plata) y por eso las cuatro comparten el mismo body: pedir
    cuerpos distintos por endpoint obligaría al front a recordar cuál acepta qué.
    """

    #: Cuándo se movió la plata. `None` = hoy.
    fecha: date | None = None

    _valida_fecha = field_validator("fecha")(validar_fecha_movimiento)


class ChequeConciliarBody(BaseModel):
    """La fecha acá es OBLIGATORIA, a diferencia de las transiciones.

    El CHECK `ck_cheques_conciliado_con_fecha` de la 0011 la exige, y con razón: una conciliación
    sin fecha no se puede auditar, que es todo el punto de conciliar.
    """

    fecha: date

    _valida_fecha = field_validator("fecha")(validar_fecha_movimiento)


class ChequeResponse(BaseModel):
    """Lo que devuelve una transición: el papel como quedó, y la plata que movió.

    Trae los saldos porque una transición puede tocar DOS formas a la vez (cobrar saca de la
    cartera y acredita en efectivo o transferencia), y devolver un solo número obligaría al front a
    pedir el saldo de nuevo para saber qué mostrar.
    """

    cheque: ChequeLeer
    #: Los movimientos de caja que escribió, vacío si la transición no movió plata (depositar, o
    #: cualquier transición de un cheque emitido).
    movimientos: list[MovimientoCajaResponse]
    #: El saldo de TODAS las formas, ya recalculado.
    saldos: dict[str, Decimal]
