"""El test más importante del producto: el aislamiento multi-tenant se cumple en la BASE.

No verifica el `where org_id=...` del código de la app (esa es la primera barrera). Verifica
la SEGUNDA barrera, la red de seguridad: que aunque el código se olvidara de filtrar —o el
LLM del asistente generara un SELECT de más— Postgres no deja cruzar de tenant.

Por eso las queries de acá NO llevan `where org_id`. Solo fijan el GUC y confían en RLS. Si
RLS no estuviera, estos tests verían datos de más y fallarían.
"""

from uuid import uuid4

import pytest
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError

from app.core.db import ORG_GUC, USER_GUC, set_guc


def _fijar_org(conn, org_id) -> None:
    """Fija el tenant de la transacción, igual que hace get_tenant en cada request."""
    set_guc(conn, ORG_GUC, str(org_id))


def test_app_user_solo_ve_las_filas_de_su_tenant(app_conn, tenants):
    """La política `using`: con el GUC en A, un SELECT sin filtro devuelve SOLO filas de A."""
    _fijar_org(app_conn, tenants.a)
    codigos_a = app_conn.execute(text("select codigo from articulos")).scalars().all()

    _fijar_org(app_conn, tenants.b)
    codigos_b = app_conn.execute(text("select codigo from articulos")).scalars().all()

    assert codigos_a == ["COD-A"]
    assert codigos_b == ["COD-B"]


def test_sin_org_fijada_no_ve_nada(app_conn, tenants):
    """Fail-CLOSED, no fail-open: sin GUC, `current_setting(..., true)` es NULL y no matchea
    ninguna fila. Si el circuito de tenant fallara, la app no ve datos — nunca los de todos."""
    filas = app_conn.execute(text("select count(*) from articulos")).scalar_one()
    assert filas == 0


def test_with_check_bloquea_insertar_en_otro_tenant(app_conn, tenants):
    """La política `with check`: parado en A, no se puede escribir una fila de B.

    `using` controla qué VES; `with check` controla qué ESCRIBÍS. Sin esto, un tenant podría
    inyectar filas dentro de otro aunque no pudiera leerlas."""
    _fijar_org(app_conn, tenants.a)

    with pytest.raises(DBAPIError) as exc:
        app_conn.execute(
            text(
                "insert into articulos (org_id, codigo, detalle) "
                "values (:o, 'X-1', 'Intruso')"
            ),
            {"o": tenants.b},
        )

    assert "row-level security" in str(exc.value).lower()


def test_vista_stock_respeta_rls_por_security_invoker(app_conn, tenants):
    """El caso sutil: `stock` es una VISTA sobre `stock_movimientos`.

    Sin `security_invoker=true`, la vista correría con permisos de su owner y SALTEARÍA el RLS
    del kardex — un tenant vería el stock de otro. Con security_invoker corre como quien la
    consulta y el RLS se aplica. Sembramos A=7 y B=3: cada uno debe ver solo su cantidad."""
    _fijar_org(app_conn, tenants.a)
    stock_a = app_conn.execute(text("select cantidad from stock")).scalars().all()

    _fijar_org(app_conn, tenants.b)
    stock_b = app_conn.execute(text("select cantidad from stock")).scalars().all()

    assert stock_a == [7]
    assert stock_b == [3]


def test_remitos_procesados_respeta_rls(app_conn, tenants):
    """`remitos_procesados` (ingesta visual) es tabla de tenant como cualquier otra.

    Importa además por una razón propia: es el candado de idempotencia. Si un tenant pudiera
    ver los hashes de otro, sabría qué remitos cargó su competencia."""
    _fijar_org(app_conn, tenants.a)
    app_conn.execute(
        text(
            "insert into remitos_procesados (org_id, imagen_hash, renglones_count) "
            "values (:o, :h, 1)"
        ),
        {"o": tenants.a, "h": "a" * 64},
    )

    _fijar_org(app_conn, tenants.b)
    assert app_conn.execute(text("select count(*) from remitos_procesados")).scalar_one() == 0

    _fijar_org(app_conn, tenants.a)
    hashes = app_conn.execute(text("select imagen_hash from remitos_procesados")).scalars().all()
    assert hashes == ["a" * 64]


def test_remitos_procesados_with_check_bloquea_otro_tenant(app_conn, tenants):
    """Parado en A no se puede sembrar un remito dentro de B."""
    _fijar_org(app_conn, tenants.a)

    with pytest.raises(DBAPIError) as exc:
        app_conn.execute(
            text(
                "insert into remitos_procesados (org_id, imagen_hash, renglones_count) "
                "values (:o, :h, 1)"
            ),
            {"o": tenants.b, "h": "b" * 64},
        )

    assert "row-level security" in str(exc.value).lower()


def test_remitos_hash_unico_por_org_pero_no_entre_orgs(app_conn, tenants):
    """El candado de idempotencia: el MISMO remito no entra dos veces en la misma org...

    ...pero dos orgs distintas SÍ pueden tener el mismo hash. No es un caso hipotético:
    dos repuesteras que le compran al mismo distribuidor pueden recibir remitos idénticos.
    Si el unique fuera solo sobre imagen_hash, la segunda org no podría cargar el suyo."""
    insert = text(
        "insert into remitos_procesados (org_id, imagen_hash, renglones_count) "
        "values (:o, :h, 1)"
    )

    _fijar_org(app_conn, tenants.a)
    app_conn.execute(insert, {"o": tenants.a, "h": "c" * 64})

    # Mismo hash, misma org → rebota contra el unique.
    # El savepoint es necesario: el IntegrityError envenena la transacción, y sin aislarlo
    # no se podría seguir usando la conexión para verificar la otra mitad.
    sp = app_conn.begin_nested()
    with pytest.raises(DBAPIError) as exc:
        app_conn.execute(insert, {"o": tenants.a, "h": "c" * 64})
    assert "uq_remitos_org_hash" in str(exc.value)
    sp.rollback()

    # Mismo hash, OTRA org → entra sin drama.
    _fijar_org(app_conn, tenants.b)
    app_conn.execute(insert, {"o": tenants.b, "h": "c" * 64})
    assert app_conn.execute(text("select count(*) from remitos_procesados")).scalar_one() == 1


def test_membresia_solo_ve_la_propia(app_conn, tenants):
    """`miembros` es la excepción: filtra por USUARIO, no por org (es la tabla que resuelve el
    org_id, se lee ANTES de conocerlo). Con dos membresías de usuarios distintos sembradas,
    user_a debe ver SOLO la suya — es lo que impide que un token descubra la org de otro."""
    set_guc(app_conn, USER_GUC, str(tenants.user_a))
    orgs_vistas = app_conn.execute(text("select org_id from miembros")).scalars().all()
    assert orgs_vistas == [tenants.a]

    # Un usuario sin ninguna membresía no ve nada (esto es lo que dispara el 403 en get_tenant).
    set_guc(app_conn, USER_GUC, str(uuid4()))
    assert app_conn.execute(text("select count(*) from miembros")).scalar_one() == 0
