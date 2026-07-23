from datetime import date, datetime
from decimal import Decimal
from uuid import UUID

from sqlalchemy import (
    BigInteger,
    Date,
    ForeignKey,
    Numeric,
    String,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.core.base import Base, BigIntPk, Cantidad, Money2, OrgMixin, TimestampMixin


class Compra(Base, OrgMixin, TimestampMixin):
    """Cabecera de una compra a un proveedor. APPEND-ONLY: registrada no se edita.

    Es la contraparte de `Comprobante` del lado proveedor. A diferencia de una venta, NO lleva
    numeración interna correlativa: una compra la identifica el número del comprobante DEL
    PROVEEDOR (su factura/remito). El unique `(org, proveedor, numero_comprobante)` evita cargar
    dos veces la misma factura —mismo criterio que `remitos_procesados`— y es el árbitro de
    concurrencia (dos cargas simultáneas: una gana, la otra se lleva un IntegrityError → 409).

    Los totales (`neto`, `iva`, `total`) se GUARDAN a propósito: son un snapshot congelado del
    documento, no un saldo acumulado. La corrección sería una nota de débito/crédito futura.
    """

    __tablename__ = "compras"
    __table_args__ = (
        UniqueConstraint(
            "org_id", "proveedor_id", "numero_comprobante", name="uq_compras_org_prov_numero"
        ),
    )

    id: Mapped[BigIntPk]
    proveedor_id: Mapped[int] = mapped_column(
        ForeignKey("proveedores.id", ondelete="RESTRICT"), index=True
    )
    deposito_id: Mapped[int] = mapped_column(
        ForeignKey("depositos.id", ondelete="RESTRICT"), index=True
    )
    #: El número de la factura/remito del proveedor (no un correlativo nuestro).
    numero_comprobante: Mapped[str] = mapped_column(String(40))
    fecha: Mapped[date] = mapped_column(Date, server_default=func.current_date())
    condicion: Mapped[str] = mapped_column(String(10))  # 'contado' | 'cta_cte'

    neto: Mapped[Money2]
    iva: Mapped[Money2]
    total: Mapped[Money2]

    creado_por: Mapped[UUID | None]


class CompraItem(Base, OrgMixin, TimestampMixin):
    """Un renglón de compra. APPEND-ONLY, como su cabecera.

    IVA EXPLÍCITO por renglón (crédito fiscal): `alicuota_iva` se congela acá con su `importe_iva`
    y `total_renglon`. El `costo_unitario` es lo que pagamos por unidad (neto), y es lo que pisa el
    costo del artículo al confirmar la compra.
    """

    __tablename__ = "compra_items"

    id: Mapped[BigIntPk]
    compra_id: Mapped[int] = mapped_column(ForeignKey("compras.id", ondelete="CASCADE"), index=True)
    articulo_id: Mapped[int] = mapped_column(
        ForeignKey("articulos.id", ondelete="RESTRICT"), index=True
    )
    cantidad: Mapped[Cantidad]
    costo_unitario: Mapped[Money2]  # neto, sin IVA
    alicuota_iva: Mapped[Decimal] = mapped_column(Numeric(5, 2), default=Decimal("21.00"))
    importe_iva: Mapped[Money2]
    total_renglon: Mapped[Money2]


class ProvCtaCteMovimiento(Base, OrgMixin):
    """Libro mayor de cuenta corriente de PROVEEDOR: lo que le debemos. APPEND-ONLY.

    Mismo esqueleto que `CtaCteMovimiento` (cliente), pero el significado va invertido: acá el
    saldo positivo es deuda NUESTRA. Una compra a crédito carga un Debe (debemos más), un pago
    carga un Haber (debemos menos). El saldo NO es una columna: es la VISTA `proveedor_saldo`
    (SUM(debe) - SUM(haber)). Un error se corrige con un contra-movimiento de ajuste, jamás
    editando el pasado — el trigger de la base lo hace cumplir.

    Nota para el NL2SQL: aquí `debe` = lo que le debemos al proveedor (opuesto al ledger de
    cliente, donde `debe` = lo que el cliente nos debe). La fórmula del saldo es la misma.
    """

    __tablename__ = "prov_cta_cte_movimientos"

    id: Mapped[BigIntPk]
    proveedor_id: Mapped[int] = mapped_column(
        ForeignKey("proveedores.id", ondelete="RESTRICT"), index=True
    )
    fecha: Mapped[date] = mapped_column(Date, server_default=func.current_date())
    #: 'compra' | 'pago' | 'ajuste'
    tipo: Mapped[str] = mapped_column(String(20))
    debe: Mapped[Money2] = mapped_column(default=Decimal("0"))
    haber: Mapped[Money2] = mapped_column(default=Decimal("0"))
    ref_tipo: Mapped[str | None] = mapped_column(String(30))
    ref_id: Mapped[int | None] = mapped_column(BigInteger)
    creado_en: Mapped[datetime] = mapped_column(server_default=func.now())
    creado_por: Mapped[UUID | None]


class ProveedorSaldo(Base):
    """VISTA: saldo = SUM(debe) - SUM(haber) por proveedor. Positivo = lo que le debemos.

    `security_invoker = true` es OBLIGATORIO: sin eso la vista corre con los permisos de su owner
    y SALTEA el RLS de `prov_cta_cte_movimientos`, dejando a un tenant ver el saldo de otro.
    `info={"is_view": True}` la excluye del autogenerate de Alembic.

    Entidad de SOLO LECTURA. Un proveedor sin movimientos NO aparece acá (saldo 0 implícito).
    """

    __tablename__ = "proveedor_saldo"
    __table_args__ = {"info": {"is_view": True}}

    org_id: Mapped[UUID] = mapped_column(primary_key=True)
    proveedor_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    saldo: Mapped[Money2]
