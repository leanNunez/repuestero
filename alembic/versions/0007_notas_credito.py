"""Notas de crédito: reverso append-only de una venta emitida

Agrega `notas_credito` + `nota_credito_items`: la cabecera y renglones de una NC, que revierte
una venta (devuelve stock y, si era a crédito, baja la deuda). Un comprobante emitido no se
edita; se corrige con una de estas.

Ambas tablas son APPEND-ONLY (REVOKE + trigger, igual que comprobantes y el kardex). Además
ensancha `cta_cte_movimientos.tipo` a varchar(20) para que entre el nuevo tipo 'nota_credito'.

Revision ID: 0007
Revises: 0006
Create Date: 2026-07-23
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0007"
down_revision: str | None = "0006"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

#: El rol DML de la app. Hardcodeado a propósito: cada migración es un snapshot y solo conoce
#: lo que ella misma crea (ver la nota en 0001_esquema_nucleo.py).
APP_ROLE = "app_user"


def _org_fk(nullable: bool = False):
    return sa.Column(
        "org_id",
        sa.Uuid(),
        sa.ForeignKey("organizaciones.id", ondelete="CASCADE"),
        nullable=nullable,
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


def _blindar_append_only(tabla: str) -> None:
    """Append-only de verdad: la base lo hace cumplir, no la buena voluntad del código.

    Una nota de crédito es un hecho contable: no se edita ni se borra. Mismo criterio (y misma
    técnica) que `comprobantes` en la 0005.
    """
    op.execute(f"revoke update, delete on {tabla} from {APP_ROLE};")
    op.execute(
        f"""
        create trigger trg_{tabla}_append_only
        before update or delete on {tabla}
        for each row execute function nota_credito_append_only();
        """
    )


def upgrade() -> None:
    op.create_table(
        "notas_credito",
        sa.Column("id", sa.BigInteger(), sa.Identity(always=True), primary_key=True),
        _org_fk(),
        sa.Column(
            "ref_comprobante_id",
            sa.BigInteger(),
            sa.ForeignKey("comprobantes.id", ondelete="RESTRICT"),
            nullable=False,
            index=True,
        ),
        sa.Column(
            "cliente_id",
            sa.BigInteger(),
            sa.ForeignKey("clientes.id", ondelete="RESTRICT"),
            nullable=False,
            index=True,
        ),
        sa.Column(
            "deposito_id",
            sa.BigInteger(),
            sa.ForeignKey("depositos.id", ondelete="RESTRICT"),
            nullable=False,
            index=True,
        ),
        sa.Column("tipo", sa.String(10), nullable=False),
        sa.Column("pto_venta", sa.Integer(), nullable=False),
        sa.Column("numero", sa.BigInteger(), nullable=False),
        sa.Column("fecha", sa.Date(), nullable=False, server_default=sa.func.current_date()),
        sa.Column("condicion", sa.String(10), nullable=False),
        sa.Column("neto", sa.Numeric(14, 2), nullable=False),
        sa.Column("iva", sa.Numeric(14, 2), nullable=False),
        sa.Column("total", sa.Numeric(14, 2), nullable=False),
        sa.Column("creado_en", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("creado_por", sa.Uuid(), nullable=True),
        sa.UniqueConstraint(
            "org_id", "tipo", "pto_venta", "numero", name="uq_notas_credito_org_tipo_pv_num"
        ),
    )

    op.create_table(
        "nota_credito_items",
        sa.Column("id", sa.BigInteger(), sa.Identity(always=True), primary_key=True),
        _org_fk(),
        sa.Column(
            "nota_credito_id",
            sa.BigInteger(),
            sa.ForeignKey("notas_credito.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column(
            "articulo_id",
            sa.BigInteger(),
            sa.ForeignKey("articulos.id", ondelete="RESTRICT"),
            nullable=False,
            index=True,
        ),
        sa.Column("cantidad", sa.Numeric(14, 2), nullable=False),
        sa.Column("precio_unitario", sa.Numeric(14, 2), nullable=False),
        sa.Column("alicuota_iva", sa.Numeric(5, 2), nullable=False, server_default="21.00"),
        sa.Column("importe_iva", sa.Numeric(14, 2), nullable=False),
        sa.Column("total_renglon", sa.Numeric(14, 2), nullable=False),
        sa.Column("creado_en", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    for tabla in ("notas_credito", "nota_credito_items"):
        _aplicar_rls(tabla)

    # Una sola función de trigger, compartida por las tablas append-only de notas de crédito.
    op.execute(
        """
        create or replace function nota_credito_append_only() returns trigger as $$
        begin
            raise exception 'las notas de crédito son append-only: no se editan ni se borran';
        end;
        $$ language plpgsql;
        """
    )
    _blindar_append_only("notas_credito")
    _blindar_append_only("nota_credito_items")

    # El nuevo tipo 'nota_credito' (12 chars) no entra en el varchar(10) original.
    op.alter_column(
        "cta_cte_movimientos",
        "tipo",
        type_=sa.String(20),
        existing_type=sa.String(10),
        existing_nullable=False,
    )

    # Sin GRANT explícito: los `alter default privileges` de la 0003 ya le dan a app_user (DML)
    # y app_readonly (SELECT) permisos sobre las tablas que cree este rol.


def downgrade() -> None:
    op.alter_column(
        "cta_cte_movimientos",
        "tipo",
        type_=sa.String(10),
        existing_type=sa.String(20),
        existing_nullable=False,
    )
    op.execute("drop table if exists nota_credito_items cascade;")
    op.execute("drop table if exists notas_credito cascade;")
    op.execute("drop function if exists nota_credito_append_only();")
