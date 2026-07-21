"""Cuenta corriente: libro mayor append-only + saldo como vista

Agrega `cta_cte_movimientos` (Debe/Haber por cliente) y la vista `cliente_saldo`
(SUM(debe) - SUM(haber)). El saldo NUNCA es una columna mutable: es la vista. Es la lección
más cara del legacy (saldo guardado Y recalculado que se desincroniza, §4.6).

El ledger es APPEND-ONLY (REVOKE + trigger): un error se corrige con un movimiento de ajuste,
nunca editando el pasado.

Revision ID: 0006
Revises: 0005
Create Date: 2026-07-21
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0006"
down_revision: str | None = "0005"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

APP_ROLE = "app_user"
READONLY_ROLE = "app_readonly"


def upgrade() -> None:
    op.create_table(
        "cta_cte_movimientos",
        sa.Column("id", sa.BigInteger(), sa.Identity(always=True), primary_key=True),
        sa.Column(
            "org_id",
            sa.Uuid(),
            sa.ForeignKey("organizaciones.id", ondelete="CASCADE"),
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
        sa.Column("fecha", sa.Date(), nullable=False, server_default=sa.func.current_date()),
        sa.Column("tipo", sa.String(10), nullable=False),  # venta | cobranza | ajuste
        sa.Column("debe", sa.Numeric(14, 2), nullable=False, server_default="0"),
        sa.Column("haber", sa.Numeric(14, 2), nullable=False, server_default="0"),
        sa.Column("ref_tipo", sa.String(30), nullable=True),
        sa.Column("ref_id", sa.BigInteger(), nullable=True),
        sa.Column("creado_en", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("creado_por", sa.Uuid(), nullable=True),
    )

    # RLS estándar por tenant (mismo patrón que el resto).
    op.execute("alter table cta_cte_movimientos enable row level security;")
    op.execute("alter table cta_cte_movimientos force row level security;")
    op.execute(
        """
        create policy tenant_isolation on cta_cte_movimientos
            using      (org_id = current_setting('app.current_org_id', true)::uuid)
            with check (org_id = current_setting('app.current_org_id', true)::uuid);
        """
    )

    # Append-only: la base lo hace cumplir, no la buena voluntad del código.
    op.execute(f"revoke update, delete on cta_cte_movimientos from {APP_ROLE};")
    op.execute(
        """
        create or replace function cta_cte_append_only() returns trigger as $$
        begin
            raise exception
                'la cuenta corriente es append-only: corregí con un movimiento de ajuste';
        end;
        $$ language plpgsql;
        """
    )
    op.execute(
        """
        create trigger trg_cta_cte_append_only
        before update or delete on cta_cte_movimientos
        for each row execute function cta_cte_append_only();
        """
    )

    # Saldo = SUMA del libro mayor. `security_invoker = true` para que el RLS del ledger se
    # aplique (si no, la vista correría como owner y cruzaría tenants).
    op.execute(
        """
        create view cliente_saldo with (security_invoker = true) as
        select org_id,
               cliente_id,
               sum(debe) - sum(haber) as saldo
        from cta_cte_movimientos
        group by org_id, cliente_id;
        """
    )
    op.execute(f"grant select on cliente_saldo to {APP_ROLE};")
    op.execute(f"grant select on cliente_saldo to {READONLY_ROLE};")


def downgrade() -> None:
    op.execute("drop view if exists cliente_saldo;")
    op.execute("drop table if exists cta_cte_movimientos cascade;")
    op.execute("drop function if exists cta_cte_append_only();")
