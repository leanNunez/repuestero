from datetime import datetime
from decimal import Decimal
from typing import Annotated
from uuid import UUID

from sqlalchemy import BigInteger, DateTime, ForeignKey, Identity, Numeric, func
from sqlalchemy.orm import DeclarativeBase, Mapped, declared_attr, mapped_column
from sqlalchemy.types import Uuid

#: Clave primaria de todo el dominio.
#:
#: `Identity(always=True)` = `bigint generated always as identity`. Postgres serializa
#: la asignación del número: dos cajas facturando a la vez NUNCA pueden obtener el mismo
#: id. Es el reemplazo directo del `Select Max(ID)+1` del legacy, que es la causa raíz de
#: los comprobantes duplicados (ver docs/analisis-legacy.md §4.1).
#:
#: `Mapped[int]` a secas daría SERIAL, que permite insertar el id a mano y pisarlo.
#: `always` lo prohíbe a nivel motor.
BigIntPk = Annotated[int, mapped_column(BigInteger, Identity(always=True), primary_key=True)]

#: Plata. numeric(14,4) para costos (necesitan precisión en el cálculo de márgenes).
Money = Annotated[Decimal, mapped_column(Numeric(14, 4))]

#: Importes de venta ya redondeados a centavos.
Money2 = Annotated[Decimal, mapped_column(Numeric(14, 2))]

#: Cantidades de stock (admite fraccionarios: metros de cable, litros de aceite).
Cantidad = Annotated[Decimal, mapped_column(Numeric(14, 2))]


class Base(DeclarativeBase):
    """Base declarativa.

    `type_annotation_map` es lo que garantiza la regla no negociable: cualquier
    campo tipado como Decimal aterriza en Postgres como numeric, jamás como float.
    """

    type_annotation_map = {
        Decimal: Numeric(14, 4),
        datetime: DateTime(timezone=True),
        UUID: Uuid(as_uuid=True),
    }


class TimestampMixin:
    creado_en: Mapped[datetime] = mapped_column(server_default=func.now())


class OrgMixin:
    """Toda tabla del dominio lleva org_id. Sin excepciones.

    Es la columna sobre la que se apoyan TODAS las políticas de RLS.
    """

    @declared_attr.directive
    def org_id(cls) -> Mapped[UUID]:
        return mapped_column(
            ForeignKey("organizaciones.id", ondelete="CASCADE"),
            index=True,
            nullable=False,
        )
