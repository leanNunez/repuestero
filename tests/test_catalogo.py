"""Listado del catálogo: paginación (offset/total) + filtros server-side (rubro, marca).

Contra Postgres real (necesita la DB levantada), como el resto de la suite: la paginación y los
filtros conviven con RLS, y lo que se verifica acá es que el `total` cuente SOLO el resultado
filtrado del tenant —nunca los artículos de otra org, aunque compartan rubro o marca—.

Dos estilos, como el repo:
- Patrón A (service directo como app_user, sujeto a RLS): la lógica de paginación/filtro/RLS.
- Patrón B (TestClient con JWT): el contrato HTTP —el shape {items,total} y las rutas nuevas—.
"""

from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from uuid import uuid4

import jwt
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.catalogo import service
from app.catalogo.models import Articulo
from app.core import db as core_db
from app.core.config import get_settings
from app.core.db import ORG_GUC, set_guc
from app.core.models import Miembro, Organizacion
from app.main import app
from tests.conftest import APP_URL, OWNER_URL

# (codigo, detalle, marca, rubro) — org A. Rubros: FILTROS x3, FRENOS x1, ENCENDIDO x1 (total 5).
# Marcas: Mann x2, Fram x1, Ferodo x1, NGK x1. Da para paginar de a 2 y filtrar por ambos ejes.
ARTICULOS_A = [
    ("A-001", "FILTRO DE ACEITE MANN W1", "Mann", "FILTROS"),
    ("A-002", "FILTRO DE AIRE MANN C1", "Mann", "FILTROS"),
    ("A-003", "FILTRO DE ACEITE FRAM PH1", "Fram", "FILTROS"),
    ("A-004", "PASTILLA DE FRENO FERODO F1", "Ferodo", "FRENOS"),
    ("A-005", "BUJIA NGK B1", "NGK", "ENCENDIDO"),
]


@pytest.fixture(scope="module")
def catalogo(migrated_db):
    """Siembra org A (5 artículos) y org B (uno que comparte rubro y marca con A) como owner."""
    org_a, org_b = uuid4(), uuid4()
    eng = create_engine(OWNER_URL)
    with Session(eng) as s:
        s.add(Organizacion(id=org_a, nombre="Org A"))
        s.add(Organizacion(id=org_b, nombre="Org B"))
        s.flush()
        for codigo, detalle, marca, rubro in ARTICULOS_A:
            s.add(Articulo(org_id=org_a, codigo=codigo, detalle=detalle, marca=marca, rubro=rubro))
        # Comparte rubro FILTROS y marca Mann con A: si RLS o el filtro por org fallaran, se
        # colaría en el listado y/o inflaría el `total` de A.
        s.add(
            Articulo(
                org_id=org_b,
                codigo="B-001",
                detalle="FILTRO SECRETO ORG B",
                marca="Mann",
                rubro="FILTROS",
            )
        )
        s.commit()
    eng.dispose()
    return SimpleNamespace(a=org_a, b=org_b)


@pytest.fixture
def sesion_a(catalogo):
    """Sesión como app_user (sujeto a RLS) con el tenant A fijado, en una transacción efímera."""
    eng = create_engine(APP_URL)
    with Session(eng) as s:
        set_guc(s, ORG_GUC, str(catalogo.a))
        yield s
    eng.dispose()


def _codigos(items):
    return [a.codigo for a in items]


# --------------------------------------------------------------------------- paginación
def test_paginacion_devuelve_pagina_y_total(sesion_a, catalogo):
    items, total = service.listar_articulos(sesion_a, catalogo.a, limite=2, offset=0)
    assert total == 5  # el total es del resultado completo, no de la página
    # Orden estable por descripción: BUJIA…, FILTRO DE ACEITE FRAM…, FILTRO DE ACEITE MANN…
    assert _codigos(items) == ["A-005", "A-003"]


def test_paginacion_segunda_pagina_sin_solapamiento(sesion_a, catalogo):
    p1, _ = service.listar_articulos(sesion_a, catalogo.a, limite=2, offset=0)
    p2, total = service.listar_articulos(sesion_a, catalogo.a, limite=2, offset=2)
    assert total == 5
    assert _codigos(p2) == ["A-001", "A-002"]  # FILTRO DE ACEITE MANN, FILTRO DE AIRE MANN
    assert set(_codigos(p1)).isdisjoint(_codigos(p2))


def test_paginacion_ultima_pagina_parcial(sesion_a, catalogo):
    items, total = service.listar_articulos(sesion_a, catalogo.a, limite=2, offset=4)
    assert total == 5
    assert _codigos(items) == ["A-004"]  # PASTILLA DE FRENO, la última alfabéticamente


# --------------------------------------------------------------------------- filtros
def test_filtro_por_rubro_afecta_items_y_total(sesion_a, catalogo):
    items, total = service.listar_articulos(sesion_a, catalogo.a, rubro="FILTROS", limite=50)
    assert total == 3  # no 5: el total refleja el filtro
    assert {a.rubro for a in items} == {"FILTROS"}


def test_filtro_por_marca_afecta_items_y_total(sesion_a, catalogo):
    items, total = service.listar_articulos(sesion_a, catalogo.a, marca="Mann", limite=50)
    assert total == 2
    assert {a.marca for a in items} == {"Mann"}


def test_filtros_combinados_rubro_y_marca(sesion_a, catalogo):
    items, total = service.listar_articulos(
        sesion_a, catalogo.a, rubro="FILTROS", marca="Fram", limite=50
    )
    assert total == 1
    assert _codigos(items) == ["A-003"]


def test_buscar_combinado_con_filtro(sesion_a, catalogo):
    items, total = service.listar_articulos(
        sesion_a, catalogo.a, buscar="AIRE", rubro="FILTROS", limite=50
    )
    assert total == 1
    assert _codigos(items) == ["A-002"]


# --------------------------------------------------------------------------- RLS
def test_total_y_items_respetan_rls(sesion_a, catalogo):
    """El artículo de org B (mismo rubro y marca) no aparece ni se cuenta en el total de A."""
    items, total = service.listar_articulos(sesion_a, catalogo.a, rubro="FILTROS", limite=50)
    assert total == 3  # los 3 de A; NO el de B aunque también sea FILTROS/Mann
    assert "B-001" not in _codigos(items)


# --------------------------------------------------------------------------- rubros / marcas
def test_listar_rubros_distintos_ordenados_sin_null(sesion_a, catalogo):
    assert service.listar_rubros(sesion_a, catalogo.a) == ["ENCENDIDO", "FILTROS", "FRENOS"]


def test_listar_marcas_distintas_ordenadas(sesion_a, catalogo):
    assert service.listar_marcas(sesion_a, catalogo.a) == ["Ferodo", "Fram", "Mann", "NGK"]


# =========================================================================== HTTP (contrato)
@pytest.fixture(scope="module")
def org_http(migrated_db):
    org_id, user_id = uuid4(), uuid4()
    eng = create_engine(OWNER_URL)
    with Session(eng) as s:
        s.add(Organizacion(id=org_id, nombre="Org HTTP"))
        s.flush()
        s.add(
            Articulo(
                org_id=org_id, codigo="H-001", detalle="FILTRO MANN", marca="Mann", rubro="FILTROS"
            )
        )
        s.add(
            Articulo(
                org_id=org_id, codigo="H-002", detalle="BUJIA NGK", marca="NGK", rubro="ENCENDIDO"
            )
        )
        s.add(Miembro(org_id=org_id, user_id=user_id, rol="admin"))  # sin esto get_tenant da 403
        s.commit()
    eng.dispose()
    return SimpleNamespace(id=org_id, user=user_id)


@pytest.fixture
def cliente(org_http, monkeypatch):
    """TestClient con el JWT del usuario sembrado y la sesión apuntando a la DB de test."""
    monkeypatch.setattr(core_db, "SessionLocal", lambda: Session(create_engine(APP_URL)))
    s = get_settings()
    token = jwt.encode(
        {
            "sub": str(org_http.user),
            "aud": s.supabase_jwt_audience,
            "exp": datetime.now(UTC) + timedelta(hours=1),
        },
        s.supabase_jwt_secret,
        algorithm="HS256",
    )
    with TestClient(app) as c:
        c.headers.update({"Authorization": f"Bearer {token}"})
        yield c


def test_endpoint_articulos_devuelve_shape_paginado(cliente):
    r = cliente.get("/catalogo/articulos?limite=1&offset=0")
    assert r.status_code == 200
    body = r.json()
    assert set(body) == {"items", "total"}
    assert isinstance(body["items"], list) and len(body["items"]) == 1
    assert body["total"] == 2  # el total es del catálogo, no de la página


def test_endpoint_articulos_filtra_por_rubro(cliente):
    r = cliente.get("/catalogo/articulos?rubro=ENCENDIDO")
    assert r.status_code == 200
    body = r.json()
    assert body["total"] == 1
    assert body["items"][0]["codigo"] == "H-002"


def test_endpoint_rubros_y_marcas(cliente):
    rubros = cliente.get("/catalogo/rubros")
    marcas = cliente.get("/catalogo/marcas")
    assert rubros.status_code == 200 and rubros.json() == ["ENCENDIDO", "FILTROS"]
    assert marcas.status_code == 200 and marcas.json() == ["Mann", "NGK"]


def test_endpoint_sin_token_es_401():
    with TestClient(app) as c:
        assert c.get("/catalogo/articulos").status_code == 401
