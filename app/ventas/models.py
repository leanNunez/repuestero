from datetime import date, datetime
from decimal import Decimal
from uuid import UUID

from sqlalchemy import (
    BigInteger,
    Date,
    ForeignKey,
    Integer,
    Numeric,
    String,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.core.base import Base, BigIntPk, Cantidad, Money2, OrgMixin, TimestampMixin


class Numerador(Base, OrgMixin):
    """Contador de números de comprobante por (tipo, punto de venta).

    Es el reemplazo directo del `Max(Numero)+1` del legacy (docs/analisis-legacy.md §4.1), la
    causa raíz de los comprobantes duplicados cuando dos cajas facturan a la vez. El número se
    asigna con `SELECT ultimo ... FOR UPDATE` (ver `service.asignar_numero`): Postgres serializa
    el acceso a la fila, así que dos ventas concurrentes se forman en cola en vez de pisarse.

    NO es append-only: la columna `ultimo` se muta bajo el lock. Lo que garantiza la unicidad
    del número EMITIDO es ese bloqueo más el unique de `comprobantes(org, tipo, pto_venta, numero)`.
    """

    __tablename__ = "numeradores"
    __table_args__ = (
        UniqueConstraint("org_id", "tipo", "pto_venta", name="uq_numeradores_org_tipo_pv"),
    )

    id: Mapped[BigIntPk]
    tipo: Mapped[str] = mapped_column(String(10))
    pto_venta: Mapped[int] = mapped_column(Integer)
    ultimo: Mapped[int] = mapped_column(BigInteger, default=0)


class Comprobante(Base, OrgMixin, TimestampMixin):
    """Cabecera de una venta. APPEND-ONLY: emitido no se edita.

    Los totales (`neto`, `iva`, `total`) se GUARDAN a propósito. No viola "saldo como vista":
    esa regla es para saldos ACUMULADOS que crecen con cada movimiento. El total de un
    comprobante es un snapshot congelado al emitir —igual que `Comprobantes.Neto/Total` del
    legacy—, inmutable. La corrección es una nota de crédito futura, nunca un UPDATE.
    """

    __tablename__ = "comprobantes"
    __table_args__ = (
        UniqueConstraint(
            "org_id", "tipo", "pto_venta", "numero", name="uq_comprobantes_org_tipo_pv_num"
        ),
    )

    id: Mapped[BigIntPk]
    cliente_id: Mapped[int] = mapped_column(
        ForeignKey("clientes.id", ondelete="RESTRICT"), index=True
    )
    deposito_id: Mapped[int] = mapped_column(
        ForeignKey("depositos.id", ondelete="RESTRICT"), index=True
    )
    tipo: Mapped[str] = mapped_column(String(10))  # 'FAC', 'PRE', ...
    pto_venta: Mapped[int] = mapped_column(Integer)
    numero: Mapped[int] = mapped_column(BigInteger)
    fecha: Mapped[date] = mapped_column(Date, server_default=func.current_date())
    condicion: Mapped[str] = mapped_column(String(10))  # 'contado' | 'cta_cte'

    neto: Mapped[Money2]
    iva: Mapped[Money2]
    total: Mapped[Money2]

    creado_por: Mapped[UUID | None]


class ComprobanteItem(Base, OrgMixin, TimestampMixin):
    """Un renglón de venta. APPEND-ONLY, como su cabecera.

    IVA EXPLÍCITO por renglón (regla no negociable): `alicuota_iva` se copia del artículo y se
    congela acá, con su `importe_iva` y `total_renglon` calculados. Nunca en "baldes" opacos
    tipo VGB1..VGB4 del legacy (docs/analisis-legacy.md §4.8).
    """

    __tablename__ = "comprobante_items"

    id: Mapped[BigIntPk]
    comprobante_id: Mapped[int] = mapped_column(
        ForeignKey("comprobantes.id", ondelete="CASCADE"), index=True
    )
    articulo_id: Mapped[int] = mapped_column(
        ForeignKey("articulos.id", ondelete="RESTRICT"), index=True
    )
    cantidad: Mapped[Cantidad]
    precio_unitario: Mapped[Money2]  # neto, sin IVA
    alicuota_iva: Mapped[Decimal] = mapped_column(Numeric(5, 2), default=Decimal("21.00"))
    importe_iva: Mapped[Money2]
    total_renglon: Mapped[Money2]


class CtaCteMovimiento(Base, OrgMixin):
    """Libro mayor de cuenta corriente del cliente. APPEND-ONLY.

    Acá está la lección MÁS CARA del legacy: guardaba el saldo en una columna Y lo recalculaba,
    y las dos versiones se desincronizaban (docs/analisis-legacy.md §4.6). Por eso el saldo NO es
    una columna: es la VISTA `cliente_saldo` (SUM(debe) - SUM(haber)). Una sola fuente de verdad.

    Dos columnas debe/haber en vez de una con signo, como el `ClientesCtaCte` del legacy: una
    venta a crédito es un Debe, una cobranza un Haber. Un error se corrige con un contra-movimiento
    de ajuste, jamás editando el pasado — el trigger de la base lo hace cumplir.
    """

    __tablename__ = "cta_cte_movimientos"

    id: Mapped[BigIntPk]
    cliente_id: Mapped[int] = mapped_column(
        ForeignKey("clientes.id", ondelete="RESTRICT"), index=True
    )
    fecha: Mapped[date] = mapped_column(Date, server_default=func.current_date())
    tipo: Mapped[str] = mapped_column(String(10))  # 'venta' | 'cobranza' | 'ajuste'
    debe: Mapped[Money2] = mapped_column(default=Decimal("0"))
    haber: Mapped[Money2] = mapped_column(default=Decimal("0"))
    ref_tipo: Mapped[str | None] = mapped_column(String(30))
    ref_id: Mapped[int | None] = mapped_column(BigInteger)
    creado_en: Mapped[datetime] = mapped_column(server_default=func.now())
    creado_por: Mapped[UUID | None]


class ClienteSaldo(Base):
    """VISTA: saldo = SUM(debe) - SUM(haber) por cliente. Nunca una columna mutable.

    `security_invoker = true` es OBLIGATORIO: sin eso la vista corre con los permisos de su owner
    y SALTEA el RLS de `cta_cte_movimientos`, dejando a un tenant ver el saldo de otro.
    `info={"is_view": True}` la excluye del autogenerate de Alembic (env.py::include_object).

    Entidad de SOLO LECTURA. Un cliente sin movimientos NO aparece acá (saldo 0 implícito).
    """

    __tablename__ = "cliente_saldo"
    __table_args__ = {"info": {"is_view": True}}

    org_id: Mapped[UUID] = mapped_column(primary_key=True)
    cliente_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    saldo: Mapped[Money2]
