from collections.abc import Iterator
from contextlib import contextmanager
from uuid import UUID

from sqlalchemy import create_engine, event, text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import get_settings

_settings = get_settings()


@event.listens_for(Engine, "connect")
def _fijar_zona_horaria(dbapi_connection, _record) -> None:
    """Toda conexión nueva arranca en la zona horaria del NEGOCIO, no en la del server.

    Está enganchado a la CLASE `Engine` y no a un engine puntual a propósito: en este repo hay más
    de cuarenta `create_engine` (tests, seeds, importador, reindex), y un `connect_args` por engine
    es exactamente la clase de cosa que el próximo se olvida. Acá alcanza con que el proceso haya
    importado este módulo.

    Por qué importa, y no es cosmético: el server corre en UTC (Supabase y el contenedor local),
    y `current_date` —que es el `server_default` de la fecha en ventas, compras, recibos y los dos
    ledgers— se evalúa en la zona de la SESIÓN. Sin esto, a partir de las 21:00 hora argentina la
    base ya está en el día siguiente: una cobranza cargada a las 21:30 se guardaba con fecha de
    mañana, y el cierre del sábado se llevaba movimientos del domingo.

    Peor todavía, había DOS relojes en desacuerdo: la base fechaba en UTC y
    `fechas.validar_fecha_movimiento` validaba con la hora local de Python. En esa franja el
    sistema guardaba solo una fecha que rechazaba si se la mandabas escrita.

    `set_config(..., false)` = alcance de SESIÓN (no de transacción, como los GUCs de RLS): tiene
    que sobrevivir a cada commit, porque describe a la conexión y no al request.

    Y por eso mismo va en AUTOCOMMIT: un `SET` de sesión igual es transaccional, así que corriendo
    en la transacción implícita que abre psycopg se perdía con el primer rollback que el pool emite
    al reciclar la conexión. Es el mismo patrón que documenta SQLAlchemy para fijar `search_path`.
    """
    autocommit_previo = dbapi_connection.autocommit
    dbapi_connection.autocommit = True
    try:
        with dbapi_connection.cursor() as cur:
            cur.execute("select set_config('TimeZone', %s, false)", (_settings.tz_negocio,))
    finally:
        dbapi_connection.autocommit = autocommit_previo


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
