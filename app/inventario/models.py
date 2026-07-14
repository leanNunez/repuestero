from datetime import datetime
from uuid import UUID

from sqlalchemy import BigInteger, ForeignKey, String, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from app.core.base import Base, BigIntPk, Cantidad, OrgMixin, TimestampMixin


class Deposito(Base, OrgMixin, TimestampMixin):
    __tablename__ = "depositos"
    __table_args__ = (UniqueConstraint("org_id", "codigo", name="uq_depositos_org_codigo"),)

    id: Mapped[BigIntPk]
    codigo: Mapped[str] = mapped_column(String(20))
    nombre: Mapped[str] = mapped_column(String(80))


class StockMovimiento(Base, OrgMixin):
    """Kardex APPEND-ONLY. La única fuente de verdad del stock.

    No hay UPDATE ni DELETE acá: un error se corrige con un movimiento de ajuste que lo
    compensa, igual que un asiento contable. El histórico queda entero y auditable.

    `cantidad` es con signo: positivo entra, negativo sale.
    """

    __tablename__ = "stock_movimientos"

    id: Mapped[BigIntPk]
    articulo_id: Mapped[int] = mapped_column(
        ForeignKey("articulos.id", ondelete="RESTRICT"), index=True
    )
    deposito_id: Mapped[int] = mapped_column(
        ForeignKey("depositos.id", ondelete="RESTRICT"), index=True
    )
    cantidad: Mapped[Cantidad]
    motivo: Mapped[str] = mapped_column(String(30))  # compra | venta | ajuste | inicial
    ref_tipo: Mapped[str | None] = mapped_column(String(30))
    ref_id: Mapped[int | None] = mapped_column(BigInteger)
    creado_en: Mapped[datetime] = mapped_column(server_default=func.now())
    creado_por: Mapped[UUID | None]


class Stock(Base):
    """VISTA, no tabla. `stock = SUM(stock_movimientos.cantidad)` por artículo y depósito.

    Acá está la lección más cara del legacy. El sistema viejo guardaba la cantidad en una
    columna mutable Y además la recalculaba con SUM: cuando un proceso se cortaba a la
    mitad, las dos versiones se desincronizaban y los números dejaban de cerrar
    (docs/analisis-legacy.md §4.6). El mismo pecado que la cuenta corriente.

    Con una vista, la desincronización es IMPOSIBLE por construcción: no hay dos copias
    del dato, hay una sola. Si algún día leer duele — no va a doler con ~2.000 artículos —
    se promueve a vista materializada sin tocar una línea del dominio.

    Entidad de SOLO LECTURA. Dos detalles críticos, ambos resueltos en la migración:

    1. La vista se crea con `security_invoker = true`. Por defecto Postgres ejecuta las
       vistas con los permisos de SU OWNER (postgres), lo que SALTEARÍA el RLS de
       `stock_movimientos` y dejaría a un tenant viendo el stock de otro. Con
       `security_invoker` la vista corre como quien la consulta y el RLS se aplica.
    2. `info={"is_view": True}` hace que `alembic/env.py` la excluya del autogenerate —
       si no, Alembic intentaría crearla como tabla.
    """

    __tablename__ = "stock"
    __table_args__ = {"info": {"is_view": True}}

    org_id: Mapped[UUID] = mapped_column(primary_key=True)
    articulo_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    deposito_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    cantidad: Mapped[Cantidad]
