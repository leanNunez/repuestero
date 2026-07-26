"""Caja y cartera de cheques

El último agujero grande de la Fase 2. Hasta acá, cobrar un recibo bajaba la cuenta corriente
del cliente pero la plata no entraba a ningún lado, y el cheque que quedó sobre el mostrador no
existía para el sistema.

- `caja_movimientos`: el libro del dinero. APPEND-ONLY, saldo como VISTA (`caja_saldo`).
- `cheques`: la cartera. NO es append-only, y es a propósito (ver abajo).

## Por qué `caja_movimientos` guarda `forma` y no hay una tabla por medio de pago

Un solo libro con la forma como DIMENSIÓN. "La caja física" —el cajón— es la vista filtrada por
`forma = 'efectivo'`; lo que entró por transferencia o tarjeta vive en el mismo libro con otra
forma. Es exactamente para lo que `app/core/formas_pago.py` dice existir: "para que el futuro
app/caja/ pueda leerlas uniformemente sin preguntar de qué lado vino el movimiento".

## Por qué `cheques` NO es append-only, si todo el resto del dominio lo es

Porque un cheque **cambia de estado por naturaleza**: entra a cartera, se deposita, se cobra o
vuelve rechazado. Eso es el ciclo de vida de un papel, no un hecho contable.

La regla del proyecto se cumple igual, y en el lugar correcto: **la PLATA no muta**. Cada
transición que mueve dinero escribe una fila NUEVA en `caja_movimientos`. El estado es del
papel; el dinero es del libro. Si `cheques` fuera append-only habría que modelar el estado como
un ledger de transiciones, que es la misma información con una tabla más y ninguna garantía
extra: el saldo nunca se lee de ahí.

## Sin backfill

Las cobranzas y los pagos anteriores a esta migración **no** generan movimientos de caja
retroactivos, por la misma razón que la 0010 no fabricó recibos: inventaría dinero que nadie
contó. Los saldos de caja arrancan en cero, y eso es la verdad.

Revision ID: 0011
Revises: 0010
Create Date: 2026-07-26
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0011"
down_revision: str | None = "0010"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

#: El rol DML de la app. Hardcodeado a propósito: cada migración es un snapshot y solo conoce
#: lo que ella misma crea (ver la nota en 0001_esquema_nucleo.py).
APP_ROLE = "app_user"

#: Copia CONGELADA de `app.core.formas_pago.FORMAS_PAGO`. No se importa: una migración no puede
#: depender de código que cambia, o dejaría de reproducir el pasado. Un test ata las dos copias.
FORMAS_PAGO = ("efectivo", "cheque", "transferencia", "tarjeta")

#: Copia CONGELADA de `app.core.conceptos_caja`. Mismo criterio que arriba.
CONCEPTOS_INGRESO = ("cobranza", "cheque_cobrado", "aporte", "otro_ingreso")
CONCEPTOS_EGRESO = (
    "pago_proveedor",
    "cheque_rechazado",
    "gasto",
    "retiro",
    "otro_egreso",
)

#: Ciclo de vida del papel. Las transiciones válidas las impone el service (0011 solo acota el
#: vocabulario): un CHECK no puede mirar el estado anterior sin un trigger, y la máquina de
#: estados es política de dominio, no del esquema.
ESTADOS_CHEQUE = ("en_cartera", "depositado", "cobrado", "rechazado", "entregado")
ORIGENES_CHEQUE = ("recibido", "emitido")


def _lista(valores: Sequence[str]) -> str:
    return ", ".join(f"'{v}'" for v in valores)


def _org_fk():
    return sa.Column(
        "org_id",
        sa.Uuid(),
        sa.ForeignKey("organizaciones.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )


def _aplicar_rls(tabla: str) -> None:
    """RLS estándar por tenant. `force` porque el owner está exento por defecto; `with check`
    además de `using` para que un tenant no pueda ESCRIBIR filas dentro de otro."""
    op.execute(f"alter table {tabla} enable row level security;")
    op.execute(f"alter table {tabla} force row level security;")
    op.execute(
        f"""
        create policy tenant_isolation on {tabla}
            using      (org_id = current_setting('app.current_org_id', true)::uuid)
            with check (org_id = current_setting('app.current_org_id', true)::uuid);
        """
    )


def upgrade() -> None:
    ingresos, egresos = _lista(CONCEPTOS_INGRESO), _lista(CONCEPTOS_EGRESO)

    op.create_table(
        "caja_movimientos",
        sa.Column("id", sa.BigInteger(), sa.Identity(always=True), primary_key=True),
        _org_fk(),
        # Cuándo se movió la plata, no cuándo se cargó. `creado_en` guarda el alta real, así que
        # el retroactivo es auditable — mismo criterio que el ledger de cuenta corriente.
        sa.Column("fecha", sa.Date(), nullable=False, server_default=sa.func.current_date()),
        # DOS columnas y no un importe con signo, igual que `cta_cte_movimientos`. Un signo
        # invita a sumarlo mal en un reporte; dos columnas hacen la vista trivial y explícita.
        sa.Column("ingreso", sa.Numeric(14, 2), nullable=False, server_default="0"),
        sa.Column("egreso", sa.Numeric(14, 2), nullable=False, server_default="0"),
        sa.Column("forma", sa.String(20), nullable=False),
        sa.Column("concepto", sa.String(30), nullable=False),
        # Texto libre del operador ("flete Andreani", "retiro para pagar el alquiler").
        sa.Column("detalle", sa.String(200), nullable=True),
        # NULL = movimiento MANUAL. Si vienen cargados, el movimiento lo emitió un documento y
        # nadie lo tipeó. Sin FK: apuntan a tablas distintas ('recibo', 'orden_pago', 'cheque'),
        # igual que `ref_tipo`/`ref_id` en los dos ledgers de cuenta corriente.
        sa.Column("ref_tipo", sa.String(20), nullable=True),
        sa.Column("ref_id", sa.BigInteger(), nullable=True),
        sa.Column("creado_en", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("creado_por", sa.Uuid(), nullable=True),
        sa.CheckConstraint(f"forma in ({_lista(FORMAS_PAGO)})", name="ck_caja_movimientos_forma"),
        sa.CheckConstraint(
            f"concepto in ({ingresos}, {egresos})", name="ck_caja_movimientos_concepto"
        ),
        # Exactamente uno de los dos lados. Un movimiento que no mueve plata es ruido, y uno que
        # mueve los dos lados a la vez es dos movimientos mal escritos.
        sa.CheckConstraint(
            "(ingreso > 0 and egreso = 0) or (egreso > 0 and ingreso = 0)",
            name="ck_caja_movimientos_un_solo_lado",
        ),
        # El invariante que hace que el vocabulario sirva de algo: un 'gasto' no puede ser un
        # ingreso. Sin esto, el catálogo sería decorativo y los reportes por concepto mentirían.
        sa.CheckConstraint(
            f"(ingreso > 0 and concepto in ({ingresos})) or "
            f"(egreso > 0 and concepto in ({egresos}))",
            name="ck_caja_movimientos_concepto_coherente",
        ),
        # Los dos juntos o los dos nulos: media referencia no apunta a nada.
        sa.CheckConstraint(
            "(ref_tipo is null) = (ref_id is null)", name="ck_caja_movimientos_ref_completa"
        ),
    )
    # El extracto se lee SIEMPRE por org y ordenado por fecha; el id desempata los peers de la
    # misma fecha. Va desde el día uno porque el patrón de acceso no es una incógnita acá.
    op.create_index("ix_caja_movimientos_org_fecha", "caja_movimientos", ["org_id", "fecha", "id"])

    op.create_table(
        "cheques",
        sa.Column("id", sa.BigInteger(), sa.Identity(always=True), primary_key=True),
        _org_fk(),
        sa.Column("origen", sa.String(10), nullable=False),
        sa.Column("importe", sa.Numeric(14, 2), nullable=False),
        sa.Column("estado", sa.String(15), nullable=False, server_default="en_cartera"),
        # NULLABLE a propósito: un renglón de forma de pago solo trae `forma` y `monto`, así que
        # al derivar el cheque desde un recibo estos datos TODAVÍA no se conocen. Completarlos es
        # tarea de la pantalla de cartera. Llevarlos en el payload del recibo es una mejora
        # posterior: cambiaría el contrato que se acaba de estabilizar.
        sa.Column("banco", sa.String(80), nullable=True),
        sa.Column("numero", sa.String(40), nullable=True),
        sa.Column("fecha_emision", sa.Date(), nullable=True),
        # La fecha a partir de la cual se puede cobrar. Es LO que hace útil a la cartera: sin
        # esto no se puede responder "qué cheques puedo depositar esta semana".
        sa.Column("fecha_cobro", sa.Date(), nullable=True),
        sa.Column("conciliado", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("fecha_conciliacion", sa.Date(), nullable=True),
        # De qué documento salió: 'recibo' (uno recibido) u 'orden_pago' (uno emitido).
        sa.Column("ref_tipo", sa.String(20), nullable=True),
        sa.Column("ref_id", sa.BigInteger(), nullable=True),
        sa.Column("creado_en", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("creado_por", sa.Uuid(), nullable=True),
        sa.CheckConstraint(f"origen in ({_lista(ORIGENES_CHEQUE)})", name="ck_cheques_origen"),
        sa.CheckConstraint(f"estado in ({_lista(ESTADOS_CHEQUE)})", name="ck_cheques_estado"),
        sa.CheckConstraint("importe > 0", name="ck_cheques_importe_positivo"),
        sa.CheckConstraint("(ref_tipo is null) = (ref_id is null)", name="ck_cheques_ref_completa"),
        # Un cheque conciliado sin fecha es una conciliación que nadie puede auditar.
        sa.CheckConstraint(
            "conciliado = false or fecha_conciliacion is not null",
            name="ck_cheques_conciliado_con_fecha",
        ),
    )
    op.create_index("ix_cheques_org_estado", "cheques", ["org_id", "estado", "fecha_cobro"])

    for tabla in ("caja_movimientos", "cheques"):
        _aplicar_rls(tabla)

    # Append-only SOLO sobre el libro del dinero. `cheques` muta por diseño (ver el docstring).
    op.execute(
        """
        create or replace function caja_append_only() returns trigger as $$
        begin
            raise exception
                'un movimiento de caja no se edita: cargá el movimiento contrario';
        end;
        $$ language plpgsql;
        """
    )
    op.execute(f"revoke update, delete on caja_movimientos from {APP_ROLE};")
    op.execute(
        """
        create trigger trg_caja_movimientos_append_only
        before update or delete on caja_movimientos
        for each row execute function caja_append_only();
        """
    )
    # `cheques` sí acepta UPDATE (la transición de estado), pero NUNCA DELETE: un cheque que
    # existió no desaparece, se marca rechazado o entregado.
    op.execute(f"revoke delete on cheques from {APP_ROLE};")

    # Saldo = SUMA del libro, POR FORMA. `security_invoker = true` para que el RLS del ledger se
    # aplique (si no, la vista correría como owner y cruzaría tenants). Espejo de `cliente_saldo`.
    op.execute(
        """
        create view caja_saldo with (security_invoker = true) as
        select org_id,
               forma,
               sum(ingreso) - sum(egreso) as saldo
        from caja_movimientos
        group by org_id, forma;
        """
    )
    op.execute(f"grant select on caja_saldo to {APP_ROLE};")
    op.execute("grant select on caja_saldo to app_readonly;")


def downgrade() -> None:
    op.execute("drop view if exists caja_saldo;")
    op.execute("drop table if exists cheques cascade;")
    op.execute("drop table if exists caja_movimientos cascade;")
    op.execute("drop function if exists caja_append_only();")
