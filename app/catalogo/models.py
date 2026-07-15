from decimal import Decimal

from pgvector.sqlalchemy import Vector
from sqlalchemy import Computed, ForeignKey, Numeric, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import TSVECTOR
from sqlalchemy.orm import Mapped, mapped_column

from app.core.base import Base, BigIntPk, Cantidad, Money, Money2, OrgMixin, TimestampMixin

#: Dimensión de paraphrase-multilingual-MiniLM-L12-v2 (fastembed). Coincide con la migración 0002.
EMBEDDING_DIM = 384


class Articulo(Base, OrgMixin, TimestampMixin):
    __tablename__ = "articulos"
    __table_args__ = (UniqueConstraint("org_id", "codigo", name="uq_articulos_org_codigo"),)

    id: Mapped[BigIntPk]
    codigo: Mapped[str] = mapped_column(String(40))
    detalle: Mapped[str] = mapped_column(String(200))

    costo: Mapped[Money] = mapped_column(default=Decimal("0"))
    costo_dolar: Mapped[Money | None]

    # IVA explícito. Vive en el artículo como DEFAULT; cuando exista el renglón de venta
    # (Fase 2) se copia al renglón y se congela ahí. Nunca en "baldes" opacos tipo
    # VGB1..VGB4 del legacy (docs/analisis-legacy.md §4.8).
    alicuota_iva: Mapped[Decimal] = mapped_column(Numeric(5, 2), default=Decimal("21.00"))

    punto_pedido: Mapped[Cantidad] = mapped_column(default=Decimal("0"))
    codigo_barra: Mapped[str | None] = mapped_column(String(60))
    marca: Mapped[str | None] = mapped_column(String(60))
    rubro: Mapped[str | None] = mapped_column(String(60))
    activo: Mapped[bool] = mapped_column(default=True)

    # Embedding semántico. Nullable: lo llena el reindex batch (ver catalogo/reindex.py), no el
    # insert — así el hot path no carga el modelo de 120MB. Búsqueda por SIGNIFICADO.
    embedding: Mapped[list[float] | None] = mapped_column(Vector(EMBEDDING_DIM), default=None)

    # tsvector GENERADO por Postgres (full-text español). Read-only y `deferred`: las queries
    # normales no lo traen. Búsqueda por TEXTO. La expresión espeja la de la migración 0002.
    busqueda: Mapped[str] = mapped_column(
        TSVECTOR,
        Computed(
            "to_tsvector('spanish', "
            "coalesce(detalle,'')||' '||coalesce(marca,'')||' '||"
            "coalesce(rubro,'')||' '||coalesce(codigo,''))",
            persisted=True,
        ),
        deferred=True,
        nullable=True,
    )


class ListaPrecio(Base, OrgMixin, TimestampMixin):
    """N listas de precio, no las 4 columnas fijas `Precio0..3` del legacy."""

    __tablename__ = "listas_precio"
    __table_args__ = (UniqueConstraint("org_id", "codigo", name="uq_listas_org_codigo"),)

    id: Mapped[BigIntPk]
    codigo: Mapped[str] = mapped_column(String(30))
    nombre: Mapped[str] = mapped_column(String(80))


class ArticuloPrecio(Base, OrgMixin, TimestampMixin):
    __tablename__ = "articulo_precios"
    __table_args__ = (
        UniqueConstraint("articulo_id", "lista_id", name="uq_precio_articulo_lista"),
    )

    id: Mapped[BigIntPk]
    articulo_id: Mapped[int] = mapped_column(
        ForeignKey("articulos.id", ondelete="CASCADE"), index=True
    )
    lista_id: Mapped[int] = mapped_column(
        ForeignKey("listas_precio.id", ondelete="CASCADE"), index=True
    )
    precio: Mapped[Money2]
    margen: Mapped[Decimal | None] = mapped_column(Numeric(6, 2), default=None)
