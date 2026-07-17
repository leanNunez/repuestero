"""Ingesta visual: remitos de proveedor cargados desde una foto

Agrega `remitos_procesados`, que hace de candado de idempotencia (un remito no se puede
cargar dos veces) y de registro de auditoría (qué aprobó el humano, cuándo y desde qué foto).

Revision ID: 0004
Revises: 0003
Create Date: 2026-07-16
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "0004"
down_revision: str | None = "0003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "remitos_procesados",
        sa.Column("id", sa.BigInteger(), sa.Identity(always=True), primary_key=True),
        sa.Column(
            "org_id",
            sa.Uuid(),
            sa.ForeignKey("organizaciones.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column("imagen_hash", sa.String(64), nullable=False),
        sa.Column(
            "proveedor_id",
            sa.BigInteger(),
            sa.ForeignKey("proveedores.id", ondelete="RESTRICT"),
            nullable=True,
            index=True,
        ),
        sa.Column("numero_remito", sa.String(40), nullable=True),
        sa.Column("fecha_remito", sa.Date(), nullable=True),
        sa.Column("total_declarado", sa.Numeric(14, 2), nullable=True),
        sa.Column("renglones_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("propuesta", postgresql.JSONB(), nullable=True),
        sa.Column("creado_en", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("creado_por", sa.Uuid(), nullable=True),
        sa.UniqueConstraint("org_id", "imagen_hash", name="uq_remitos_org_hash"),
    )

    # Segunda barrera de duplicado. El hash atrapa el doble click sobre la misma imagen;
    # esto atrapa la MISMA mercadería re-fotografiada (otra foto = otro hash). Parcial
    # porque un remito sin número no puede colisionar con nadie por número.
    op.create_index(
        "uq_remitos_org_prov_numero",
        "remitos_procesados",
        ["org_id", "proveedor_id", "numero_remito"],
        unique=True,
        postgresql_where=sa.text("numero_remito is not null"),
    )

    # RLS hardcodeada acá, no iterando la tupla del registry: esta migración solo conoce
    # las tablas que ella misma crea (ver la nota en 0001_esquema_nucleo.py).
    #
    # `force` porque el owner está exento de RLS por defecto. `with check` además de `using`
    # porque `using` controla qué filas VES y `with check` qué filas podés ESCRIBIR: sin él
    # un tenant podría insertar un remito dentro de otro.
    op.execute("alter table remitos_procesados enable row level security;")
    op.execute("alter table remitos_procesados force row level security;")
    op.execute(
        """
        create policy tenant_isolation on remitos_procesados
            using      (org_id = current_setting('app.current_org_id', true)::uuid)
            with check (org_id = current_setting('app.current_org_id', true)::uuid);
        """
    )

    # Sin GRANT explícito: scripts/init_db.sql ya deja `alter default privileges` para
    # app_user sobre las tablas que cree este rol. Mismo trato que `articulos`.


def downgrade() -> None:
    op.execute("drop table if exists remitos_procesados cascade;")
