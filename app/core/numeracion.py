"""Numeración correlativa de documentos, por (tipo, punto de venta).

Vive en `core` y no en `ventas` porque los documentos numerados ya no son solo de ese lado: las
facturas y las notas de crédito son de ventas, los recibos también, pero las ÓRDENES DE PAGO son
de compras — y `compras` no importa `ventas` ni debería empezar a hacerlo por un contador.

Es el mismo criterio que `core/fechas.py` y `core/formas_pago.py`: lo que las dos mitades del
negocio necesitan igual no puede vivir en una de las dos.
"""

from uuid import UUID

from sqlalchemy import BigInteger, Integer, String, UniqueConstraint, select
from sqlalchemy.orm import Mapped, Session, mapped_column

from app.core.base import Base, BigIntPk, OrgMixin


class Numerador(Base, OrgMixin):
    """Contador de números de documento por (tipo, punto de venta).

    Es el reemplazo directo del `Max(Numero)+1` del legacy (docs/analisis-legacy.md §4.1), la
    causa raíz de los comprobantes duplicados cuando dos cajas facturan a la vez. El número se
    asigna con `SELECT ultimo ... FOR UPDATE` (ver `asignar_numero`): Postgres serializa el acceso
    a la fila, así que dos operaciones concurrentes se forman en cola en vez de pisarse.

    NO es append-only: la columna `ultimo` se muta bajo el lock. Lo que garantiza la unicidad del
    número EMITIDO es ese bloqueo más el unique del documento sobre
    (org, tipo, pto_venta, numero) — en `comprobantes`, `notas_credito`, `recibos` y
    `ordenes_pago`.

    Cada `tipo` es un espacio de numeración propio ('FAC', 'NC', 'REC', 'OP'): los recibos no
    comparten contador con las facturas, ni las órdenes de pago con nada.
    """

    __tablename__ = "numeradores"
    __table_args__ = (
        UniqueConstraint("org_id", "tipo", "pto_venta", name="uq_numeradores_org_tipo_pv"),
    )

    id: Mapped[BigIntPk]
    tipo: Mapped[str] = mapped_column(String(10))
    pto_venta: Mapped[int] = mapped_column(Integer)
    ultimo: Mapped[int] = mapped_column(BigInteger, default=0)


def asignar_numero(session: Session, org_id: UUID, *, tipo: str, pto_venta: int) -> int:
    """Devuelve el próximo número correlativo para (tipo, punto de venta), bajo lock.

    `with_for_update()` sobre la fila del numerador serializa a dos cajas operando a la vez: la
    segunda espera a que la primera libere la fila. Es el reemplazo del `Max(Numero)+1` del legacy,
    que con dos cajas duplicaba el número. Corre DENTRO de la transacción del documento.

    En la PRIMERÍSIMA emisión de un (tipo, pto_venta) la fila no existe: se crea con `ultimo=0`.
    Dos transacciones creándola a la vez es una carrera rarísima que atrapa el unique
    `uq_numeradores_org_tipo_pv` (una gana, la otra se lleva un IntegrityError y reintenta).
    """
    fila = session.scalar(
        select(Numerador)
        .where(
            Numerador.org_id == org_id,
            Numerador.tipo == tipo,
            Numerador.pto_venta == pto_venta,
        )
        .with_for_update()
    )
    if fila is None:
        fila = Numerador(org_id=org_id, tipo=tipo, pto_venta=pto_venta, ultimo=0)
        session.add(fila)
        session.flush()

    fila.ultimo += 1
    session.flush()
    return fila.ultimo
