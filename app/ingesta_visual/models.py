from datetime import date
from uuid import UUID

from sqlalchemy import Date, ForeignKey, Index, String, UniqueConstraint, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.types import Uuid

from app.core.base import Base, BigIntPk, Money2, OrgMixin, TimestampMixin


class RemitoProcesado(Base, OrgMixin, TimestampMixin):
    """Un remito de proveedor que ya se cargó al sistema desde una foto.

    Cumple dos funciones distintas:

    1. **Idempotencia.** `uq_remitos_org_hash` es el candado: dos confirmaciones del mismo
       remito no pueden entrar. La barrera la hace cumplir el motor, no la buena voluntad
       del código — mismo criterio que `Identity(always=True)` contra `Max(id)+1`.
    2. **Auditoría.** `propuesta` guarda el payload EXACTO que el humano aprobó. Cuando
       dentro de seis meses alguien pregunte "¿quién metió este costo?", la respuesta es
       una fila: el hash de la foto, el usuario, el timestamp y los renglones tal cual se
       confirmaron.

    Las dos barreras de duplicado se complementan y ninguna alcanza sola: el hash atrapa el
    doble click sobre la misma imagen, pero re-fotografiar el mismo papel da otro hash. Para
    eso está el unique parcial sobre (org, proveedor, numero_remito) — ese dato sale de OCR
    y puede venir mal, pero es editable en la pantalla de revisión, así que para cuando se
    escribe ya lo confirmó un humano.

    La imagen NO se guarda: solo su hash. Blob storage está fuera de alcance.
    """

    __tablename__ = "remitos_procesados"
    __table_args__ = (
        UniqueConstraint("org_id", "imagen_hash", name="uq_remitos_org_hash"),
        Index(
            "uq_remitos_org_prov_numero",
            "org_id",
            "proveedor_id",
            "numero_remito",
            unique=True,
            postgresql_where=text("numero_remito is not null"),
        ),
    )

    id: Mapped[BigIntPk]
    #: sha256 de los BYTES de la imagen, no del string base64.
    imagen_hash: Mapped[str] = mapped_column(String(64))
    proveedor_id: Mapped[int | None] = mapped_column(
        ForeignKey("proveedores.id", ondelete="RESTRICT"), index=True
    )
    numero_remito: Mapped[str | None] = mapped_column(String(40))
    fecha_remito: Mapped[date | None] = mapped_column(Date())
    #: Lo que declaraba el papel. Checksum contra errores de OCR, no un dato contable.
    total_declarado: Mapped[Money2 | None]
    renglones_count: Mapped[int] = mapped_column(default=0)
    propuesta: Mapped[dict | None] = mapped_column(JSONB)
    creado_por: Mapped[UUID | None] = mapped_column(Uuid(as_uuid=True))
