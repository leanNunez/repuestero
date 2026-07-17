from collections.abc import Iterator
from contextlib import contextmanager
from uuid import UUID

from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import get_settings

_settings = get_settings()

engine = create_engine(_settings.database_url, pool_pre_ping=True, future=True)
SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)

#: GUCs que leen las políticas de RLS. Un solo nombre, un solo lugar.
ORG_GUC = "app.current_org_id"
USER_GUC = "app.current_user_id"

#: Engine read-only (rol app_readonly). Perezoso: solo el asistente lo necesita, y así importar
#: db.py no falla en entornos donde DATABASE_READONLY_URL no está configurada.
_readonly_engine = None


def readonly_engine():
    global _readonly_engine
    if _readonly_engine is None:
        if not _settings.database_readonly_url:
            raise RuntimeError(
                "DATABASE_READONLY_URL no configurada — la requiere el asistente NL2SQL"
            )
        _readonly_engine = create_engine(
            _settings.database_readonly_url, pool_pre_ping=True, future=True
        )
    return _readonly_engine


def set_guc(session: Session, guc: str, value: str) -> None:
    """Fija un GUC con alcance de TRANSACCIÓN (el tercer argumento `true` de set_config).

    Al hacer commit o rollback el valor se descarta. Eso es lo que lo hace seguro con
    connection pooling: una conexión reciclada nunca arrastra el tenant del request
    anterior.

    Se usa `set_config()` con parámetros ligados en vez de `SET LOCAL` porque
    `SET LOCAL` no admite placeholders — habría que concatenar el valor dentro del
    string de SQL, que es exactamente cómo se abre un agujero de inyección.
    """
    session.execute(text("select set_config(:guc, :val, true)"), {"guc": guc, "val": value})


@contextmanager
def readonly_tenant_session(
    org_id: UUID, user_id: UUID | None = None, *, timeout_ms: int = 5000
) -> Iterator[Session]:
    """Sesión SOLO-LECTURA con el tenant fijado. Acá corre el SQL que genera el LLM.

    Tres rejas superpuestas, la primera es la única que de verdad importa:
    1. El rol (app_readonly) NO tiene permisos de escritura: un DELETE lo rechaza el motor.
    2. `transaction_read_only = on`: la transacción entera es de lectura (defensa en profundidad).
    3. `statement_timeout`: una consulta que se cuelga no tumba la base.
    Y como cualquier sesión, el GUC de tenant la encierra en su org vía RLS.

    Nunca hace commit (no hay nada que persistir): siempre rollback al salir.
    """
    session = Session(bind=readonly_engine())
    try:
        if user_id is not None:
            set_guc(session, USER_GUC, str(user_id))
        set_guc(session, ORG_GUC, str(org_id))
        # set_config con is_local=true: alcance de transacción, se descarta al terminar.
        session.execute(text("select set_config('transaction_read_only', 'on', true)"))
        session.execute(
            text("select set_config('statement_timeout', :ms, true)"),
            {"ms": str(timeout_ms)},
        )
        yield session
    finally:
        session.rollback()
        session.close()


@contextmanager
def tenant_session(org_id: UUID, user_id: UUID | None = None) -> Iterator[Session]:
    """Sesión con el tenant fijado para toda la transacción.

    Todo lo que corra acá dentro está encerrado por RLS en ese org_id. Ni un bug del
    dominio, ni un LLM que genere SQL de más, pueden cruzar de tenant: la barrera está
    en la base, no en el código de la app.
    """
    session = SessionLocal()
    try:
        if user_id is not None:
            set_guc(session, USER_GUC, str(user_id))
        set_guc(session, ORG_GUC, str(org_id))
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()
