from sqlalchemy import ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.core.base import Base, BigIntPk, OrgMixin, TimestampMixin


class Vehiculo(Base, OrgMixin, TimestampMixin):
    __tablename__ = "vehiculos"
    __table_args__ = (
        UniqueConstraint(
            "org_id", "marca", "modelo", "anio_desde", "anio_hasta", "motor", "version",
            name="uq_vehiculos_identidad",
        ),
    )

    id: Mapped[BigIntPk]
    marca: Mapped[str] = mapped_column(String(40))
    modelo: Mapped[str] = mapped_column(String(60))
    anio_desde: Mapped[int | None]
    anio_hasta: Mapped[int | None]
    motor: Mapped[str | None] = mapped_column(String(40))
    version: Mapped[str | None] = mapped_column(String(60))


class ArticuloAplicacion(Base, OrgMixin, TimestampMixin):
    """Qué repuesto sirve para qué vehículo. EL diferencial del producto.

    El legacy diseñó estas tablas y NUNCA cargó un solo registro (Vehiculos en 0).
    Por eso `origen` y `confirmado` existen desde el día uno: la compatibilidad se va a
    poblar mayormente con IA a partir de descripciones y catálogos, y ese dato entra
    como SUGERENCIA (`confirmado = false`) hasta que alguien del mostrador la valida.
    Sin esas dos columnas, dato inferido y dato verificado quedan indistinguibles — y ahí
    se pudre la confianza en el sistema entero.
    """

    __tablename__ = "articulo_aplicaciones"
    __table_args__ = (
        UniqueConstraint("articulo_id", "vehiculo_id", name="uq_aplicacion_articulo_vehiculo"),
    )

    id: Mapped[BigIntPk]
    articulo_id: Mapped[int] = mapped_column(
        ForeignKey("articulos.id", ondelete="CASCADE"), index=True
    )
    vehiculo_id: Mapped[int] = mapped_column(
        ForeignKey("vehiculos.id", ondelete="CASCADE"), index=True
    )
    nota: Mapped[str | None] = mapped_column(String(200))
    origen: Mapped[str] = mapped_column(String(30), default="manual")
    confirmado: Mapped[bool] = mapped_column(default=False)
