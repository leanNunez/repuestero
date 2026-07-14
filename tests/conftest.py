"""Infra de tests que corre contra un Postgres REAL.

RLS es una feature del motor: contra SQLite no existe. Testear el aislamiento
multi-tenant sin Postgres sería testear humo. Por eso estos tests necesitan la base
levantada (`docker compose up -d db`).

La base de tests es efímera y aparte de `repuestos` (la de dev): se crea, se migra, se
usa y se tira. Nunca ensucia datos reales y cada corrida arranca de cero.

El truco que hace testeable el RLS: hay DOS roles.
  - `postgres` es SUPERUSER → bypassea RLS. Con él sembramos orgs y datos libremente.
  - `app_user` es NOSUPERUSER sin BYPASSRLS → está sujeto a RLS igual que la app en prod.
Todo lo que verificamos se consulta como `app_user`. Es el rol bajo prueba.
"""

import os
from types import SimpleNamespace
from uuid import uuid4

import pytest
from sqlalchemy import create_engine, text

# Bases de conexión (sin nombre de db). Overridables por env para CI o puertos distintos.
_OWNER_BASE = os.environ.get("TEST_OWNER_URL", "postgresql+psycopg://postgres:postgres@localhost:5432")
_APP_BASE = os.environ.get("TEST_APP_URL", "postgresql+psycopg://app_user:app_password@localhost:5432")
_TEST_DB = os.environ.get("TEST_DB_NAME", "repuestos_test")

OWNER_URL = f"{_OWNER_BASE}/{_TEST_DB}"
APP_URL = f"{_APP_BASE}/{_TEST_DB}"

# El app y alembic leen la config de estas env vars. Se fijan ANTES de importar la app
# (conftest se importa antes que cualquier módulo de test) para que apunten a la base de
# tests y no a la de dev.
os.environ["DATABASE_URL"] = APP_URL
os.environ["MIGRATIONS_DATABASE_URL"] = OWNER_URL
os.environ.setdefault("SUPABASE_JWT_SECRET", "test-secret-solo-para-tests")


def _maintenance_engine():
    """Conexión a la db `postgres` (siempre existe) para crear/tirar la base de tests.

    AUTOCOMMIT porque CREATE/DROP DATABASE no puede correr dentro de una transacción.
    """
    return create_engine(f"{_OWNER_BASE}/postgres", isolation_level="AUTOCOMMIT")


@pytest.fixture(scope="session")
def migrated_db():
    """Crea la base de tests desde cero, la migra y la deja lista. La tira al terminar."""
    maint = _maintenance_engine()
    with maint.connect() as conn:
        # `app_user` es un rol de CLUSTER: normalmente ya lo creó scripts/init_db.sql en el
        # primer arranque del contenedor. Lo creamos defensivamente por si el volumen es viejo.
        conn.execute(
            text(
                """
                do $$
                begin
                    if not exists (select 1 from pg_roles where rolname = 'app_user') then
                        create role app_user with login password 'app_password'
                            nosuperuser nocreatedb nocreaterole noinherit;
                    end if;
                end $$;
                """
            )
        )
        conn.execute(text(f"drop database if exists {_TEST_DB} with (force)"))
        conn.execute(text(f"create database {_TEST_DB}"))
    maint.dispose()

    # Los default privileges son POR BASE: hay que replicarlos acá (scripts/init_db.sql solo
    # los aplica a la base `repuestos`). Deben fijarse ANTES de migrar para que las tablas que
    # cree Alembic hereden los permisos DML de app_user.
    owner = create_engine(OWNER_URL)
    with owner.begin() as conn:
        conn.execute(text("grant usage on schema public to app_user"))
        conn.execute(
            text(
                "alter default privileges for role postgres in schema public "
                "grant select, insert, update, delete on tables to app_user"
            )
        )
        conn.execute(
            text(
                "alter default privileges for role postgres in schema public "
                "grant usage, select on sequences to app_user"
            )
        )
    owner.dispose()

    # Migración real: mismo camino que en prod (env.py lee MIGRATIONS_DATABASE_URL → base test).
    from alembic import command
    from alembic.config import Config

    command.upgrade(Config("alembic.ini"), "head")

    yield

    maint = _maintenance_engine()
    with maint.connect() as conn:
        conn.execute(text(f"drop database if exists {_TEST_DB} with (force)"))
    maint.dispose()


@pytest.fixture(scope="session")
def tenants(migrated_db):
    """Dos orgs con datos, sembradas como SUPERUSER (bypassea RLS).

    Cada org tiene un artículo, un depósito y movimientos de stock. Devuelve los ids para que
    los tests verifiquen que app_user solo alcanza los de SU tenant.
    """
    org_a, org_b = uuid4(), uuid4()
    user_a, user_b = uuid4(), uuid4()
    eng = create_engine(OWNER_URL)
    datos = SimpleNamespace(a=org_a, b=org_b, user_a=user_a, user_b=user_b)

    miembros = {org_a: user_a, org_b: user_b}
    with eng.begin() as conn:
        for org, nombre in ((org_a, "Org A"), (org_b, "Org B")):
            conn.execute(
                text("insert into organizaciones (id, nombre) values (:id, :n)"),
                {"id": org, "n": nombre},
            )
            conn.execute(
                text("insert into miembros (org_id, user_id, rol) values (:o, :u, 'admin')"),
                {"o": org, "u": miembros[org]},
            )
            art_id = conn.execute(
                text(
                    "insert into articulos (org_id, codigo, detalle) "
                    "values (:o, :c, :d) returning id"
                ),
                {"o": org, "c": f"COD-{nombre[-1]}", "d": f"Filtro {nombre}"},
            ).scalar_one()
            dep_id = conn.execute(
                text(
                    "insert into depositos (org_id, codigo, nombre) "
                    "values (:o, 'CEN', 'Central') returning id"
                ),
                {"o": org},
            ).scalar_one()
            # Stock resultante distinto por org (A=7, B=3) para distinguirlos sin ambigüedad.
            cantidad = 7 if org == org_a else 3
            conn.execute(
                text(
                    "insert into stock_movimientos (org_id, articulo_id, deposito_id, "
                    "cantidad, motivo) values (:o, :a, :d, :q, 'inicial')"
                ),
                {"o": org, "a": art_id, "d": dep_id, "q": cantidad},
            )

    eng.dispose()
    return datos


@pytest.fixture
def app_conn(migrated_db):
    """Conexión como `app_user` (sujeto a RLS), en una transacción que se descarta al final.

    El rollback deja la base intacta entre tests y descarta el GUC de tenant (que tiene alcance
    de transacción). Cada test arranca sin org fijada.
    """
    eng = create_engine(APP_URL)
    conn = eng.connect()
    trans = conn.begin()
    try:
        yield conn
    finally:
        trans.rollback()
        conn.close()
        eng.dispose()
