from datetime import date, datetime
from decimal import Decimal
from uuid import UUID

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    Date,
    ForeignKey,
    ForeignKeyConstraint,
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

    Ese ajuste lo escribe `service.registrar_ajuste`, de dos maneras: revirtiendo un movimiento
    existente (el monto lo espeja el service, `ref_tipo='ajuste_de'`) o a mano. En los dos casos
    `motivo` es obligatorio, y lo exige un CHECK de la base (0009).
    """

    __tablename__ = "cta_cte_movimientos"

    id: Mapped[BigIntPk]
    cliente_id: Mapped[int] = mapped_column(
        ForeignKey("clientes.id", ondelete="RESTRICT"), index=True
    )
    fecha: Mapped[date] = mapped_column(Date, server_default=func.current_date())
    #: 'venta' | 'cobranza' | 'ajuste' | 'nota_credito'
    tipo: Mapped[str] = mapped_column(String(20))
    debe: Mapped[Money2] = mapped_column(default=Decimal("0"))
    haber: Mapped[Money2] = mapped_column(default=Decimal("0"))
    ref_tipo: Mapped[str | None] = mapped_column(String(30))
    ref_id: Mapped[int | None] = mapped_column(BigInteger)
    #: Por qué se ajustó. Obligatorio SOLO en `tipo='ajuste'` (CHECK en la 0009): las filas
    #: históricas y las automáticas (venta, cobranza) no tienen uno.
    motivo: Mapped[str | None] = mapped_column(String(200))
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


class Recibo(Base, OrgMixin):
    """Comprobante de un cobro a un cliente. APPEND-ONLY: emitido no se edita.

    Es el documento que le faltaba a la cuenta corriente. Antes de existir, una cobranza escribía
    un Haber suelto con `ref_tipo`/`ref_id` en NULL, mientras la venta y la nota de crédito sí
    referenciaban el suyo. El movimiento de una cobranza apunta acá con `ref_tipo='recibo'`.

    NO tiene columna `anulado`, y no es un olvido. Un recibo no se anula por sí mismo: se revierte
    el MOVIMIENTO que generó, con `service.registrar_ajuste`, y el estado "anulado" queda derivado
    (existe una reversa del movimiento que apunta a este recibo). Misma filosofía que el saldo:
    estado calculado, nunca columna mutable que pueda desincronizarse del ledger.

    `total` se GUARDA a propósito, igual que en `Comprobante`: es un snapshot congelado al emitir,
    no un acumulado. Un recibo es papel que dice "recibí $X" — el número tiene que ser
    autocontenido. Que el detalle de formas de pago sume EXACTO ese total lo hace cumplir un
    constraint trigger diferido de la base (0010), no solo el service.

    Numeración correlativa propia (`tipo='REC'`) con el mismo `Numerador` que las ventas, así que
    los recibos no comparten contador con las facturas.
    """

    __tablename__ = "recibos"
    __table_args__ = (
        UniqueConstraint(
            "org_id", "tipo", "pto_venta", "numero", name="uq_recibos_org_tipo_pv_num"
        ),
        #: Destino de la FK compuesta de `ReciboFormaPago`. Redundante como unicidad (`id` ya es
        #: PK), pero Postgres exige un unique sobre las columnas exactas que referencia una FK.
        UniqueConstraint("org_id", "id", name="uq_recibos_org_id"),
        CheckConstraint("total > 0", name="ck_recibos_total_positivo"),
    )

    id: Mapped[BigIntPk]
    cliente_id: Mapped[int] = mapped_column(
        ForeignKey("clientes.id", ondelete="RESTRICT"), index=True
    )
    tipo: Mapped[str] = mapped_column(String(10))  # 'REC'
    pto_venta: Mapped[int] = mapped_column(Integer)
    numero: Mapped[int] = mapped_column(BigInteger)
    fecha: Mapped[date] = mapped_column(Date, server_default=func.current_date())
    total: Mapped[Money2]
    creado_en: Mapped[datetime] = mapped_column(server_default=func.now())
    creado_por: Mapped[UUID | None]


class ReciboFormaPago(Base, OrgMixin):
    """Con qué se cobró un recibo: efectivo, cheque, transferencia o tarjeta. APPEND-ONLY.

    Es 1:N y no una columna en el recibo porque el pago mixto es real en el mostrador (5.000 en
    efectivo y un cheque por 15.000), y porque cuando llegue el módulo de caja CADA RENGLÓN se
    convierte en un movimiento de caja o en un cheque de la cartera. Por eso tampoco hay unique
    (recibo, forma): dos cheques distintos son dos renglones legítimos.

    En esta etapa `cheque` es solo la etiqueta con su monto; banco, número y fecha de cobro llegan
    con `app/caja/`.

    La FK a `recibos` es COMPUESTA (org_id, recibo_id), a diferencia de `ComprobanteItem`. Con una
    FK simple un renglón podría apuntar al recibo de OTRA organización: el trigger que valida la
    suma corre bajo RLS, no vería ese recibo, y dejaría pasar el renglón en silencio.
    """

    __tablename__ = "recibo_formas_pago"
    __table_args__ = (
        ForeignKeyConstraint(
            ["org_id", "recibo_id"],
            ["recibos.org_id", "recibos.id"],
            name="fk_recibo_formas_pago_recibos",
            ondelete="CASCADE",
        ),
        CheckConstraint(
            "forma in ('efectivo', 'cheque', 'transferencia', 'tarjeta')",
            name="ck_recibo_formas_pago_forma",
        ),
        CheckConstraint("monto > 0", name="ck_recibo_formas_pago_monto_positivo"),
    )

    id: Mapped[BigIntPk]
    recibo_id: Mapped[int] = mapped_column(BigInteger, index=True)
    #: Ver `app.core.formas_pago.FORMAS_PAGO`. La base lo hace cumplir con un CHECK.
    forma: Mapped[str] = mapped_column(String(20))
    monto: Mapped[Money2]
    creado_en: Mapped[datetime] = mapped_column(server_default=func.now())


class NotaCredito(Base, OrgMixin, TimestampMixin):
    """Cabecera de una nota de crédito. APPEND-ONLY, como el comprobante que corrige.

    Es la forma correcta —y única— de revertir una venta ya emitida: el comprobante no se edita
    ni se borra, se le emite una NC que devuelve el stock y (si era a crédito) baja la deuda.
    `ref_comprobante_id` apunta a la venta original; `condicion` la espeja para saber si toca la
    cuenta corriente. Los totales son un snapshot congelado, igual que en `Comprobante`.

    Tiene su propia numeración correlativa (`tipo='NC'`), asignada con el mismo `Numerador` que
    las ventas. La suma de NCs de una venta nunca puede exceder lo vendido (lo valida el service).
    """

    __tablename__ = "notas_credito"
    __table_args__ = (
        UniqueConstraint(
            "org_id", "tipo", "pto_venta", "numero", name="uq_notas_credito_org_tipo_pv_num"
        ),
    )

    id: Mapped[BigIntPk]
    ref_comprobante_id: Mapped[int] = mapped_column(
        ForeignKey("comprobantes.id", ondelete="RESTRICT"), index=True
    )
    cliente_id: Mapped[int] = mapped_column(
        ForeignKey("clientes.id", ondelete="RESTRICT"), index=True
    )
    deposito_id: Mapped[int] = mapped_column(
        ForeignKey("depositos.id", ondelete="RESTRICT"), index=True
    )
    tipo: Mapped[str] = mapped_column(String(10))  # 'NC'
    pto_venta: Mapped[int] = mapped_column(Integer)
    numero: Mapped[int] = mapped_column(BigInteger)
    fecha: Mapped[date] = mapped_column(Date, server_default=func.current_date())
    condicion: Mapped[str] = mapped_column(String(10))  # espejo del original: 'contado' | 'cta_cte'

    neto: Mapped[Money2]
    iva: Mapped[Money2]
    total: Mapped[Money2]

    creado_por: Mapped[UUID | None]


class NotaCreditoItem(Base, OrgMixin, TimestampMixin):
    """Un renglón de nota de crédito. APPEND-ONLY.

    El `precio_unitario` y la `alicuota_iva` se COPIAN del renglón original de la venta: no se
    puede acreditar a un precio distinto al que se cobró. `cantidad` es lo que se acredita de ese
    artículo (total o parcial).
    """

    __tablename__ = "nota_credito_items"

    id: Mapped[BigIntPk]
    nota_credito_id: Mapped[int] = mapped_column(
        ForeignKey("notas_credito.id", ondelete="CASCADE"), index=True
    )
    articulo_id: Mapped[int] = mapped_column(
        ForeignKey("articulos.id", ondelete="RESTRICT"), index=True
    )
    cantidad: Mapped[Cantidad]
    precio_unitario: Mapped[Money2]  # copiado del renglón original, neto sin IVA
    alicuota_iva: Mapped[Decimal] = mapped_column(Numeric(5, 2), default=Decimal("21.00"))
    importe_iva: Mapped[Money2]
    total_renglon: Mapped[Money2]
