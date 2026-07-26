"""Que la base y Python estén de acuerdo en qué día es hoy.

Suena obvio y no lo era. El server corre en UTC (Supabase y el contenedor local), y `current_date`
—el `server_default` de la fecha en ventas, compras, recibos y los dos ledgers— se evalúa en la
zona de la SESIÓN. A partir de las 21:00 hora argentina la base ya está en el día siguiente:

- una cobranza cargada a las 21:30 en el mostrador se guardaba con fecha de MAÑANA, y el cierre
  del sábado se llevaba movimientos del domingo;
- y como `fechas.validar_fecha_movimiento` validaba con la hora local de Python, el sistema
  guardaba solo una fecha que RECHAZABA si se la mandabas escrita.

El síntoma visible era que tres tests de `test_cta_cte.py` fallaban entre las 21:00 y la
medianoche y pasaban el resto del día — y en CI nunca, porque corre en UTC.

Estos tests son invariantes de la hora a la que corren: comparan los dos relojes entre sí, no
contra una fecha escrita a mano.
"""

from datetime import date, timedelta

import pytest
from sqlalchemy import create_engine, text

from app.core import db as core_db  # noqa: F401 — importarlo registra el listener de la zona
from app.core.config import get_settings
from app.core.fechas import DIAS_RETROACTIVIDAD, hoy, validar_fecha_movimiento
from tests.conftest import APP_URL, OWNER_URL


@pytest.fixture
def conn(migrated_db):
    eng = create_engine(APP_URL)
    with eng.connect() as c:
        yield c
    eng.dispose()


def test_la_conexion_arranca_en_la_zona_del_negocio(conn):
    assert conn.execute(text("select current_setting('TimeZone')")).scalar() == (
        get_settings().tz_negocio
    )


def test_la_zona_sobrevive_al_rollback(conn):
    """El bug del primer intento de arreglo.

    Un `SET` de sesión igual es transaccional: fijándolo dentro de la transacción implícita que
    abre psycopg, el primer rollback —el que el pool emite al reciclar la conexión— lo borraba y
    la sesión volvía a UTC sin avisar. Por eso el listener corre en autocommit.
    """
    antes = conn.execute(text("select current_setting('TimeZone')")).scalar()
    conn.rollback()
    conn.execute(text("select 1"))
    conn.rollback()

    assert conn.execute(text("select current_setting('TimeZone')")).scalar() == antes


def test_la_base_y_python_coinciden_en_que_dia_es_hoy(conn):
    """EL test que hubiera cazado esto.

    No compara contra una fecha escrita: compara los dos relojes que fechan movimientos. Si vuelven
    a separarse, falla a cualquier hora del día y no solo tres horas.
    """
    assert conn.execute(text("select current_date")).scalar() == hoy()


def test_un_engine_cualquiera_tambien_arranca_en_la_zona_del_negocio(migrated_db):
    """El listener está enganchado a la CLASE Engine, no a uno puntual.

    En este repo hay más de cuarenta `create_engine` (tests, seeds, importador, reindex). Si el
    arreglo dependiera de un `connect_args` por engine, el próximo que alguien escriba volvería a
    fechar en UTC. Esto verifica que un engine creado acá, a mano y contra otro rol, ya lo tiene.
    """
    eng = create_engine(OWNER_URL)
    with eng.connect() as c:
        assert c.execute(text("select current_setting('TimeZone')")).scalar() == (
            get_settings().tz_negocio
        )
    eng.dispose()


def test_el_default_de_la_base_fecha_con_el_dia_del_negocio(conn):
    """`current_date` es lo que fecha una venta, una compra, un recibo y cada movimiento del
    ledger cuando nadie manda fecha explícita."""
    assert conn.execute(text("select current_date")).scalar() == hoy()
    assert conn.execute(text("select (now() at time zone 'UTC')::date")).scalar() in (
        hoy(),
        hoy() + timedelta(days=1),  # de noche, UTC ya está en mañana: por eso existe este arreglo
    )


def test_la_fecha_de_hoy_nunca_se_rechaza_como_futura():
    """La contradicción que producía el desfase: la base fechaba en un día que el validador
    consideraba futuro, así que el sistema guardaba solo fechas que rechazaba si se las escribías.
    """
    assert validar_fecha_movimiento(hoy()) == hoy()


def test_manana_del_negocio_sigue_siendo_futuro():
    with pytest.raises(ValueError, match="futuro"):
        validar_fecha_movimiento(hoy() + timedelta(days=1))


def test_el_limite_de_retroactividad_se_mide_con_el_dia_del_negocio():
    borde = hoy() - timedelta(days=DIAS_RETROACTIVIDAD)
    assert validar_fecha_movimiento(borde) == borde

    with pytest.raises(ValueError, match="para atrás"):
        validar_fecha_movimiento(borde - timedelta(days=1))


def test_hoy_no_es_date_today_del_server_sino_el_del_negocio():
    """`date.today()` usa la zona del PROCESO, que en un contenedor es UTC. Los dos coinciden casi
    todo el día, así que el assert útil es sobre el tipo de reloj: `hoy()` no puede alejarse más de
    un día de la fecha UTC, y tiene que ser el mismo día que ve la base (ver el test de arriba)."""
    assert abs((hoy() - date.today()).days) <= 1
