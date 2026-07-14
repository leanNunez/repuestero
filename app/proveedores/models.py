from decimal import Decimal

from sqlalchemy import ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.core.base import Base, BigIntPk, Money, OrgMixin, TimestampMixin


class Proveedor(Base, OrgMixin, TimestampMixin):
    """Mínimo indispensable para Fase 0: `articulo_proveedores` necesita a quién apuntar.

    Compras y cuenta corriente de proveedor son Fase 2.
    """

    __tablename__ = "proveedores"
    __table_args__ = (UniqueConstraint("org_id", "codigo", name="uq_proveedores_org_codigo"),)

    id: Mapped[BigIntPk]
    codigo: Mapped[str] = mapped_column(String(20))
    razon_social: Mapped[str] = mapped_column(String(120))
    cuit: Mapped[str | None] = mapped_column(String(13))
    telefono: Mapped[str | None] = mapped_column(String(40))
    email: Mapped[str | None] = mapped_column(String(120))
    activo: Mapped[bool] = mapped_column(default=True)


class ArticuloProveedor(Base, OrgMixin, TimestampMixin):
    """Qué proveedores venden cada artículo, con qué código propio y a qué costo."""

    __tablename__ = "articulo_proveedores"
    __table_args__ = (
        UniqueConstraint("articulo_id", "proveedor_id", name="uq_artprov_articulo_proveedor"),
    )

    id: Mapped[BigIntPk]
    articulo_id: Mapped[int] = mapped_column(
        ForeignKey("articulos.id", ondelete="CASCADE"), index=True
    )
    proveedor_id: Mapped[int] = mapped_column(
        ForeignKey("proveedores.id", ondelete="CASCADE"), index=True
    )
    codigo_proveedor: Mapped[str | None] = mapped_column(String(40))
    costo: Mapped[Money] = mapped_column(default=Decimal("0"))
    es_preferido: Mapped[bool] = mapped_column(default=False)
