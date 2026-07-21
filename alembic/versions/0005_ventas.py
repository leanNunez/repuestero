"""Ventas: comprobantes con numeración correcta y descuento de stock

Agrega el núcleo de la Fase 2:
- `numeradores`: contador por (tipo, punto de venta), asignado con SELECT ... FOR UPDATE.
- `comprobantes` + `comprobante_items`: cabecera y renglones de venta, con IVA por renglón.

Comprobantes e items son APPEND-ONLY (blindados con REVOKE + trigger, igual que el kardex):
un comprobante emitido no se edita, se corrige con una nota de crédito (slice futuro).

Revision ID: 0005
Revises: 0004
Create Date: 2026-07-21
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0005"
down_revision: str | None = "0004"
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

    Un comprobante emitido es un hecho contable: no se edita ni se borra. Se corrige con una
    nota de crédito. Mismo criterio (y misma técnica) que `stock_movimientos` en la 0001.
    """
    op.execute(f"revoke update, delete on {tabla} from {APP_ROLE};")
    op.execute(
        f"""
        create trigger trg_{tabla}_append_only
        before update or delete on {tabla}
        for each row execute function venta_append_only();
        """
    )


def upgrade() -> None:
    op.create_table(
        "numeradores",
        sa.Column("id", sa.BigInteger(), sa.Identity(always=True), primary_key=True),
        _org_fk(),
        sa.Column("tipo", sa.String(10), nullable=False),
        sa.Column("pto_venta", sa.Integer(), nullable=False),
        sa.Column("ultimo", sa.BigInteger(), nullable=False, server_default="0"),
        sa.UniqueConstraint("org_id", "tipo", "pto_venta", name="uq_numeradores_org_tipo_pv"),
    )

    op.create_table(
        "comprobantes",
        sa.Column("id", sa.BigInteger(), sa.Identity(always=True), primary_key=True),
        _org_fk(),
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
            "org_id", "tipo", "pto_venta", "numero", name="uq_comprobantes_org_tipo_pv_num"
        ),
    )

    op.create_table(
        "comprobante_items",
        sa.Column("id", sa.BigInteger(), sa.Identity(always=True), primary_key=True),
        _org_fk(),
        sa.Column(
            "comprobante_id",
            sa.BigInteger(),
            sa.ForeignKey("comprobantes.id", ondelete="CASCADE"),
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

    for tabla in ("numeradores", "comprobantes", "comprobante_items"):
        _aplicar_rls(tabla)

    # Una sola función de trigger, compartida por las tablas append-only de ventas.
    op.execute(
        """
        create or replace function venta_append_only() returns trigger as $$
        begin
            raise exception
                'los comprobantes son append-only: corregí con una nota de crédito';
        end;
        $$ language plpgsql;
        """
    )
    _blindar_append_only("comprobantes")
    _blindar_append_only("comprobante_items")

    # Sin GRANT explícito: los `alter default privileges` de la 0003 ya le dan a app_user (DML)
    # y app_readonly (SELECT) permisos sobre las tablas que cree este rol. Mismo trato que
    # `articulos`/`remitos_procesados`.


def downgrade() -> None:
    op.execute("drop table if exists comprobante_items cascade;")
    op.execute("drop table if exists comprobantes cascade;")
    op.execute("drop table if exists numeradores cascade;")
    op.execute("drop function if exists venta_append_only();")
