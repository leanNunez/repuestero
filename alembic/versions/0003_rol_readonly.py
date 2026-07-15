"""Rol read-only app_readonly para el asistente NL2SQL

El SQL que genera el LLM corre con este rol: NOSUPERUSER, sin BYPASSRLS y con SOLO SELECT.
Es la reja DURA del asistente: aunque un prompt injection logre que el LLM genere un DELETE,
la base lo rechaza a nivel motor. Sigue sujeto a RLS igual que app_user → el GUC de tenant lo
encierra en su organización.

El rol se crea acá (idempotente) además de en scripts/init_db.sql porque init_db.sql solo corre
en el primer arranque del contenedor: una base que ya existía no lo tendría.

Revision ID: 0003
Revises: 0002
Create Date: 2026-07-14
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0003"
down_revision: str | None = "0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

READONLY = "app_readonly"


def upgrade() -> None:
    # Rol de CLUSTER (global), idempotente por si la base ya existía sin él.
    op.execute(
        f"""
        do $$
        begin
            if not exists (select 1 from pg_roles where rolname = '{READONLY}') then
                create role {READONLY} with login password 'readonly_password'
                    nosuperuser nocreatedb nocreaterole noinherit;
            end if;
        end $$;
        """
    )
    op.execute(f"grant usage on schema public to {READONLY};")
    # SELECT sobre todo lo existente (tablas Y vistas, incluida `stock`).
    op.execute(f"grant select on all tables in schema public to {READONLY};")
    # SELECT sobre lo que se cree de acá en más.
    op.execute(
        f"alter default privileges for role postgres in schema public "
        f"grant select on tables to {READONLY};"
    )


def downgrade() -> None:
    op.execute(
        f"alter default privileges for role postgres in schema public "
        f"revoke select on tables from {READONLY};"
    )
    op.execute(f"revoke select on all tables in schema public from {READONLY};")
    op.execute(f"revoke usage on schema public from {READONLY};")
    # El rol NO se dropea: es global y podría estar en uso. Revocar los permisos alcanza.
