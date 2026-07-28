from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field

from app.core.cond_fiscal import COND_FISCAL_POR_DEFECTO, CondFiscalLiteral


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


class ClienteCrear(BaseModel):
    """Alta de cliente desde la app.

    NO lleva `codigo`: lo genera el sistema (`service.generar_codigo`). Aceptarlo por el body sería
    ofrecer un control que no existe —el correlativo es del servidor— y abriría la puerta a que dos
    personas elijan el mismo y se lleven un 409 evitable.

    Los `max_length` NO son decorativos: espejan el `String(n)` de la tabla. Sin ellos un texto
    largo llega a Postgres y vuelve como `DataError` = 500, en vez de un 422 que dice qué campo se
    pasó y por cuánto.
    """

    denominacion: str = Field(min_length=1, max_length=140)
    cuit: str | None = Field(default=None, max_length=13)
    cond_fiscal: CondFiscalLiteral = COND_FISCAL_POR_DEFECTO
    limite_cta_cte: Decimal = Field(default=Decimal("0"), ge=0)
    telefono: str | None = Field(default=None, max_length=40)
    email: str | None = Field(default=None, max_length=120)
    direccion: str | None = Field(default=None, max_length=160)
