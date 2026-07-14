from decimal import Decimal

from sqlalchemy import ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.core.base import Base, BigIntPk, Money2, OrgMixin, TimestampMixin


class Cliente(Base, OrgMixin, TimestampMixin):
    __tablename__ = "clientes"
    __table_args__ = (UniqueConstraint("org_id", "codigo", name="uq_clientes_org_codigo"),)

    id: Mapped[BigIntPk]
    codigo: Mapped[str] = mapped_column(String(20))
    denominacion: Mapped[str] = mapped_column(String(140))
    cuit: Mapped[str | None] = mapped_column(String(13))
    cond_fiscal: Mapped[str] = mapped_column(String(30), default="CONSUMIDOR_FINAL")

    # Límite de crédito. La deuda NO vive acá: va a ser una vista sobre el libro mayor
    # append-only de cuenta corriente (Fase 2). Nunca una columna `saldo` mutable.
    limite_cta_cte: Mapped[Money2] = mapped_column(default=Decimal("0"))

    lista_precio_id: Mapped[int | None] = mapped_column(
        ForeignKey("listas_precio.id", ondelete="SET NULL")
    )
    telefono: Mapped[str | None] = mapped_column(String(40))
    email: Mapped[str | None] = mapped_column(String(120))
    direccion: Mapped[str | None] = mapped_column(String(160))
    activo: Mapped[bool] = mapped_column(default=True)
