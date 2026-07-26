from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.core.conceptos_caja import ConceptoManualLiteral
from app.core.fechas import validar_fecha_movimiento
from app.core.formas_pago import FormaPagoLiteral


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
