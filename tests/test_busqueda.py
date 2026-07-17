"""Búsqueda híbrida del catálogo, contra Postgres real (necesita la DB levantada).

Prueba que los dos arms tiran de lo suyo y que RRF los combina:
- SEMÁNTICO: encuentra por significado, sin las palabras exactas.
- TYPO: el arm trigram aguanta errores de tipeo.
- LÉXICO: full-text español matchea términos.
- RLS: la búsqueda queda encerrada en el tenant, como todo lo demás.

Nota: la 1ª corrida baja el modelo de fastembed (~120MB). Se cachea para las siguientes.
"""

from types import SimpleNamespace
from uuid import uuid4

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.catalogo import service
from app.catalogo.models import Articulo
from app.core.db import ORG_GUC, set_guc
from app.core.models import Organizacion
from tests.conftest import APP_URL, OWNER_URL

# (codigo, detalle, marca, rubro) — org A
ARTICULOS_A = [
    ("FIL-AC", "FILTRO DE ACEITE MANN W719/80", "Mann", "FILTROS"),
    ("AMOR-D", "AMORTIGUADOR DELANTERO MONROE G16789", "Monroe", "SUSPENSION"),
    ("BUJ-NGK", "BUJIA NGK BKR6E", "NGK", "ENCENDIDO"),
    ("CORR-D", "KIT DISTRIBUCION DAYCO 94048", "Dayco", "CORREAS"),
    ("PAST-F", "PASTILLA DE FRENO FERODO FDB1617", "Ferodo", "FRENOS"),
    ("LAMP-H4", "LAMPARA OSRAM H4 12V 60/55W", "Osram", "ILUMINACION"),
]


@pytest.fixture(scope="module")
def catalogo(migrated_db):
    """Siembra org A (catálogo) y org B (un artículo secreto) como owner, y reindexa embeddings."""
    org_a, org_b = uuid4(), uuid4()
    eng = create_engine(OWNER_URL)
    with Session(eng) as s:
        s.add(Organizacion(id=org_a, nombre="Org A"))
        s.add(Organizacion(id=org_b, nombre="Org B"))
        s.flush()  # las orgs deben existir antes de insertar los artículos que las referencian
        for codigo, detalle, marca, rubro in ARTICULOS_A:
            s.add(Articulo(org_id=org_a, codigo=codigo, detalle=detalle, marca=marca, rubro=rubro))
        # Artículo EXCLUSIVO de org B, con texto que matchearía la búsqueda de A si RLS fallara.
        s.add(
            Articulo(
                org_id=org_b,
                codigo="SECRET-B",
                detalle="FILTRO DE ACEITE SECRETO ORG B",
                marca="Mann",
                rubro="FILTROS",
            )
        )
        s.flush()
        service.reindexar_embeddings(s)  # owner ve todos los tenants → embebe todo
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


def _codigos(resultados):
    return [a.codigo for a, _ in resultados]


def test_busqueda_semantica_por_significado(sesion_a, catalogo):
    """ "para frenar el auto" no comparte palabra con "PASTILLA DE FRENO"... salvo el sentido."""
    res = service.buscar_articulos(sesion_a, catalogo.a, q="con qué freno el auto", limite=4)
    assert "PAST-F" in _codigos(res)


def test_tolerancia_a_typos(sesion_a, catalogo):
    """El arm trigram: "amortguador" (mal tipeado) encuentra el AMORTIGUADOR."""
    res = service.buscar_articulos(sesion_a, catalogo.a, q="amortguador", limite=4)
    assert "AMOR-D" in _codigos(res)


def test_busqueda_lexica(sesion_a, catalogo):
    """Full-text directo: "bujia ngk" encuentra la bujía NGK."""
    res = service.buscar_articulos(sesion_a, catalogo.a, q="bujia ngk", limite=4)
    assert _codigos(res)[0] == "BUJ-NGK"


def test_busqueda_respeta_rls(sesion_a, catalogo):
    """El artículo de org B NUNCA aparece en una búsqueda de org A, aunque matchee el texto."""
    res = service.buscar_articulos(sesion_a, catalogo.a, q="filtro de aceite", limite=20)
    codigos = _codigos(res)
    assert "FIL-AC" in codigos  # el propio sí
    assert "SECRET-B" not in codigos  # el ajeno no
