"""Dashboards de Fase 1: reposición, guardián de márgenes y KPIs.

Datos controlados en una org propia (sembrada como superuser). Se ejercita el service con una
sesión de app_user (sujeta a RLS) para verificar de paso el aislamiento multi-tenant.
"""

from decimal import Decimal
from uuid import uuid4

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session

from app.core.db import ORG_GUC, USER_GUC, set_guc
from app.dashboard import service
from tests.conftest import APP_URL, OWNER_URL


@pytest.fixture(scope="module")
def org_dash(migrated_db):
    """Org con 2 artículos: D1 (bajo punto de pedido + margen fino) y D2 (ok en ambos)."""
    org = uuid4()
    eng = create_engine(OWNER_URL)
    with eng.begin() as conn:
        conn.execute(
            text("insert into organizaciones (id, nombre) values (:o, 'Org Dashboard')"), {"o": org}
        )
        lista = conn.execute(
            text(
                "insert into listas_precio (org_id, codigo, nombre) "
                "values (:o, 'L1', 'Lista') returning id"
            ),
            {"o": org},
        ).scalar_one()
        dep = conn.execute(
            text(
                "insert into depositos (org_id, codigo, nombre) "
                "values (:o, 'CEN', 'Central') returning id"
            ),
            {"o": org},
        ).scalar_one()
        ids = {}
        # (codigo, costo, punto_pedido, stock, precio)  → D1 bajo pp y margen fino; D2 sano.
        for codigo, costo, pp, stock, precio in [
            ("D1", 100, 10, 3, 105),   # stock 3 <= pp 10; margen (105-100)/105 = 4.8% → bajo
            ("D2", 100, 5, 20, 200),   # stock 20 > pp 5; margen 50% → ok
        ]:
            aid = conn.execute(
                text(
                    "insert into articulos (org_id, codigo, detalle, costo, punto_pedido) "
                    "values (:o, :c, :d, :costo, :pp) returning id"
                ),
                {"o": org, "c": codigo, "d": f"Articulo {codigo}", "costo": costo, "pp": pp},
            ).scalar_one()
            ids[codigo] = aid
            conn.execute(
                text(
                    "insert into stock_movimientos (org_id, articulo_id, deposito_id, cantidad, motivo) "
                    "values (:o, :a, :dep, :q, 'inicial')"
                ),
                {"o": org, "a": aid, "dep": dep, "q": stock},
            )
            conn.execute(
                text(
                    "insert into articulo_precios (org_id, articulo_id, lista_id, precio, margen) "
                    "values (:o, :a, :l, :p, 0)"
                ),
                {"o": org, "a": aid, "l": lista, "p": precio},
            )
    eng.dispose()
    return org


@pytest.fixture
def sesion_app():
    eng = create_engine(APP_URL)
    with Session(eng) as s:
        yield s
    eng.dispose()


def _fijar_org(s: Session, org) -> None:
    set_guc(s, USER_GUC, str(uuid4()))
    set_guc(s, ORG_GUC, str(org))


def test_reposicion_lista_solo_los_bajo_punto_pedido(sesion_app, org_dash):
    _fijar_org(sesion_app, org_dash)
    filas = service.reposicion(sesion_app, org_dash)

    assert [f["codigo"] for f in filas] == ["D1"]  # solo D1 (D2 tiene stock de sobra)
    assert filas[0]["stock"] == Decimal("3.00")
    assert filas[0]["faltante"] == Decimal("7.00")  # 10 - 3


def test_margenes_marca_los_finos(sesion_app, org_dash):
    _fijar_org(sesion_app, org_dash)
    filas = service.margenes(sesion_app, org_dash, umbral=Decimal("20"))

    por_codigo = {f["codigo"]: f for f in filas}
    assert por_codigo["D1"]["bajo"] is True   # ~4.8% < 20
    assert por_codigo["D2"]["bajo"] is False  # 50% >= 20
    assert filas[0]["codigo"] == "D1"  # ordenado ascendente por margen (el peor primero)


def test_resumen_cuenta_bien(sesion_app, org_dash):
    _fijar_org(sesion_app, org_dash)
    r = service.resumen(sesion_app, org_dash)

    assert r["total_articulos"] == 2
    assert r["bajo_punto_pedido"] == 1
    assert r["margen_bajo"] == 1
    assert r["valor_stock"] == Decimal("2300.0000")  # 3*100 + 20*100


def test_dashboard_scopeado_por_rls(sesion_app, org_dash):
    """Con el GUC de OTRA org, el dashboard no ve NADA de org_dash (aislamiento en el motor)."""
    _fijar_org(sesion_app, uuid4())
    assert service.reposicion(sesion_app, org_dash) == []
    assert service.margenes(sesion_app, org_dash) == []
