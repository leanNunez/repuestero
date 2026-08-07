from uuid import UUID, uuid4

from sqlalchemy import ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.core.base import Base, BigIntPk, TimestampMixin


class Organizacion(Base, TimestampMixin):
    """El tenant. La raíz de todo: no existe una fila del dominio sin su org."""

    __tablename__ = "organizaciones"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    nombre: Mapped[str] = mapped_column(String(120))
    cuit: Mapped[str | None] = mapped_column(String(13))

    # Qué es la organización ante ARCA. Decide la LETRA del comprobante: un responsable inscripto
    # emite A o B según el receptor, un monotributista siempre C (`app/core/letra.py`).
    #
    # Nullable a propósito y sin backfill (migración 0014): inventarle una condición fiscal a una
    # organización es inventar un hecho fiscal. Sin esto no se puede facturar, y el error sale al
    # emitir diciendo qué falta configurar. `CONSUMIDOR_FINAL` no es un valor válido acá —lo frena
    # el CHECK— porque un consumidor final no emite comprobantes, los recibe.
    cond_fiscal: Mapped[str | None] = mapped_column(String(30))

    activa: Mapped[bool] = mapped_column(default=True)


class Miembro(Base, TimestampMixin):
    """Puente entre el usuario de Supabase Auth (`user_id` = claim `sub`) y su org.

    Deliberadamente NO usa OrgMixin: su política de RLS filtra por usuario, no por org.
    Es la única tabla que se lee ANTES de conocer el org_id — si filtrara por org_id
    sería imposible de consultar (huevo y gallina).
    """

    __tablename__ = "miembros"
    __table_args__ = (UniqueConstraint("org_id", "user_id", name="uq_miembros_org_user"),)

    id: Mapped[BigIntPk]
    org_id: Mapped[UUID] = mapped_column(
        ForeignKey("organizaciones.id", ondelete="CASCADE"), index=True
    )
    user_id: Mapped[UUID] = mapped_column(index=True)
    rol: Mapped[str] = mapped_column(String(30), default="operador")
