"""Compras: documento de compra + costos + cuenta corriente de proveedor

Agrega el lado proveedor de la Fase 2:
- `compras` + `compra_items`: cabecera y renglones de una compra, con IVA por renglón. La compra
  la identifica el número del comprobante DEL PROVEEDOR (unique por org+proveedor+numero).
- `prov_cta_cte_movimientos` (Debe/Haber por proveedor) + vista `proveedor_saldo`
  (SUM(debe) - SUM(haber) = lo que le debemos). El saldo NUNCA es una columna: es la vista.

Todo es APPEND-ONLY (REVOKE + trigger, igual que ventas y el kardex): un documento registrado no
se edita, se corrige con un contra-movimiento de ajuste o una nota futura.

Revision ID: 0008
Revises: 0007
Create Date: 2026-07-23
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0008"
down_revision: str | None = "0007"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

#: El rol DML de la app. Hardcodeado a propósito: cada migración es un snapshot y solo conoce
#: lo que ella misma crea (ver la nota en 0001_esquema_nucleo.py).
APP_ROLE = "app_user"
READONLY_ROLE = "app_readonly"


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


def _blindar_append_only(tabla: str, funcion: str) -> None:
    """Append-only de verdad: la base lo hace cumplir, no la buena voluntad del código."""
    op.execute(f"revoke update, delete on {tabla} from {APP_ROLE};")
    op.execute(
        f"""
        create trigger trg_{tabla}_append_only
        before update or delete on {tabla}
        for each row execute function {funcion}();
        """
    )


def upgrade() -> None:
    op.create_table(
        "compras",
        sa.Column("id", sa.BigInteger(), sa.Identity(always=True), primary_key=True),
        _org_fk(),
        sa.Column(
            "proveedor_id",
            sa.BigInteger(),
            sa.ForeignKey("proveedores.id", ondelete="RESTRICT"),
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
        sa.Column("numero_comprobante", sa.String(40), nullable=False),
        sa.Column("fecha", sa.Date(), nullable=False, server_default=sa.func.current_date()),
        sa.Column("condicion", sa.String(10), nullable=False),
        sa.Column("neto", sa.Numeric(14, 2), nullable=False),
        sa.Column("iva", sa.Numeric(14, 2), nullable=False),
        sa.Column("total", sa.Numeric(14, 2), nullable=False),
        sa.Column("creado_en", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("creado_por", sa.Uuid(), nullable=True),
        sa.UniqueConstraint(
            "org_id", "proveedor_id", "numero_comprobante", name="uq_compras_org_prov_numero"
        ),
    )

    op.create_table(
        "compra_items",
        sa.Column("id", sa.BigInteger(), sa.Identity(always=True), primary_key=True),
        _org_fk(),
        sa.Column(
            "compra_id",
            sa.BigInteger(),
            sa.ForeignKey("compras.id", ondelete="CASCADE"),
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
        sa.Column("costo_unitario", sa.Numeric(14, 2), nullable=False),
        sa.Column("alicuota_iva", sa.Numeric(5, 2), nullable=False, server_default="21.00"),
        sa.Column("importe_iva", sa.Numeric(14, 2), nullable=False),
        sa.Column("total_renglon", sa.Numeric(14, 2), nullable=False),
        sa.Column("creado_en", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    op.create_table(
        "prov_cta_cte_movimientos",
        sa.Column("id", sa.BigInteger(), sa.Identity(always=True), primary_key=True),
        _org_fk(),
        sa.Column(
            "proveedor_id",
            sa.BigInteger(),
            sa.ForeignKey("proveedores.id", ondelete="RESTRICT"),
            nullable=False,
            index=True,
        ),
        sa.Column("fecha", sa.Date(), nullable=False, server_default=sa.func.current_date()),
        sa.Column("tipo", sa.String(20), nullable=False),  # compra | pago | ajuste
        sa.Column("debe", sa.Numeric(14, 2), nullable=False, server_default="0"),
        sa.Column("haber", sa.Numeric(14, 2), nullable=False, server_default="0"),
        sa.Column("ref_tipo", sa.String(30), nullable=True),
        sa.Column("ref_id", sa.BigInteger(), nullable=True),
        sa.Column("creado_en", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("creado_por", sa.Uuid(), nullable=True),
    )

    for tabla in ("compras", "compra_items", "prov_cta_cte_movimientos"):
        _aplicar_rls(tabla)

    op.execute(
        """
        create or replace function compra_append_only() returns trigger as $$
        begin
            raise exception 'las compras son append-only: corregí con un ajuste o una nota';
        end;
        $$ language plpgsql;
        """
    )
    op.execute(
        """
        create or replace function prov_cta_cte_append_only() returns trigger as $$
        begin
            raise exception
                'la cuenta corriente de proveedor es append-only: corregí con un movimiento de ajuste';
        end;
        $$ language plpgsql;
        """
    )
    _blindar_append_only("compras", "compra_append_only")
    _blindar_append_only("compra_items", "compra_append_only")
    _blindar_append_only("prov_cta_cte_movimientos", "prov_cta_cte_append_only")

    # Saldo = SUMA del libro mayor. `security_invoker = true` para que el RLS del ledger se aplique
    # (si no, la vista correría como owner y cruzaría tenants). Positivo = lo que le debemos.
    op.execute(
        """
        create view proveedor_saldo with (security_invoker = true) as
        select org_id,
               proveedor_id,
               sum(debe) - sum(haber) as saldo
        from prov_cta_cte_movimientos
        group by org_id, proveedor_id;
        """
    )
    op.execute(f"grant select on proveedor_saldo to {APP_ROLE};")
    op.execute(f"grant select on proveedor_saldo to {READONLY_ROLE};")

    # Sin GRANT explícito sobre las tablas: los `alter default privileges` de la 0003 ya cubren
    # a app_user (DML) y app_readonly (SELECT).


def downgrade() -> None:
    op.execute("drop view if exists proveedor_saldo;")
    op.execute("drop table if exists prov_cta_cte_movimientos cascade;")
    op.execute("drop table if exists compra_items cascade;")
    op.execute("drop table if exists compras cascade;")
    op.execute("drop function if exists compra_append_only();")
    op.execute("drop function if exists prov_cta_cte_append_only();")
