"""Alta de clientes: código generado por el sistema y vocabulario de condición fiscal.

Dos patrones, como el resto de la suite:
- Patrón A (service contra Postgres con `app_user`, en transacción que hace rollback): la
  generación del código, donde el número exacto SÍ es determinístico.
- Patrón B (TestClient con JWT): el contrato HTTP. Estos COMMITEAN, así que nunca afirman un
  número absoluto — leen el estado antes, igual que los de caja.

Lo que no puede faltar:
- Que el correlativo sea POR ORGANIZACIÓN. Si fuera global, el cliente 1 de un comercio dependería
  de cuántos cargó otro.
- Que el código generado NO pise al importado de Paradox. Comparten `uq_clientes_org_codigo`.
- Que el vocabulario de Python y el CHECK de la base digan lo mismo. Es el único candado que tienen.
"""

from datetime import UTC, datetime, timedelta
from decimal import Decimal
from types import SimpleNamespace
from uuid import uuid4

import jwt
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.clientes import service
from app.core import db as core_db
from app.core.cond_fiscal import CONDICIONES_FISCALES
from app.core.config import get_settings
from app.core.db import ORG_GUC, set_guc
from app.core.models import Miembro, Organizacion
from app.main import app
from tests.conftest import APP_URL, OWNER_URL

#: Un CUIT real de persona jurídica con el dígito verificador correcto.
CUIT_OK = "30-71233445-9"
#: El mismo, con el último dígito cambiado. Formato válido, módulo 11 roto.
CUIT_DV_MALO = "30-71233445-1"


@pytest.fixture(scope="module")
def org(migrated_db):
    """Org vacía (sin clientes sembrados) más una vecina, para probar el aislamiento."""
    org_id, vecina_id, user_id = uuid4(), uuid4(), uuid4()
    eng = create_engine(OWNER_URL)
    with Session(eng) as s:
        s.add(Organizacion(id=org_id, nombre="Org Clientes"))
        s.add(Organizacion(id=vecina_id, nombre="Org Vecina Clientes"))
        s.flush()
        s.add(Miembro(org_id=org_id, user_id=user_id, rol="admin"))  # sin esto get_tenant da 403
        s.commit()
    eng.dispose()
    return SimpleNamespace(id=org_id, user=user_id, vecina=vecina_id)


@pytest.fixture
def sesion(org):
    """Sesión con `app_user` en una transacción que hace rollback: cada test arranca de cero."""
    eng = create_engine(APP_URL)
    conn = eng.connect()
    trans = conn.begin()
    with Session(bind=conn) as s:
        set_guc(s, ORG_GUC, str(org.id))
        yield s
    trans.rollback()
    conn.close()
    eng.dispose()


# =========================================================================== el código generado


def test_el_primer_cliente_de_una_org_arranca_en_uno(sesion, org):
    cliente = service.alta_cliente(sesion, org.id, denominacion="Taller El Rulo")

    assert cliente.codigo == "CLI-000001"


def test_el_codigo_es_correlativo_y_sin_huecos(sesion, org):
    codigos = [
        service.alta_cliente(sesion, org.id, denominacion=f"Cliente {i}").codigo for i in range(3)
    ]

    assert codigos == ["CLI-000001", "CLI-000002", "CLI-000003"]


def test_el_relleno_de_ceros_hace_que_el_orden_alfabetico_sea_el_cronologico(sesion, org):
    """`codigo` es `String(20)`: se ordena como texto. Sin padding, 'CLI-10' iría antes de 'CLI-2'."""
    codigos = [
        service.alta_cliente(sesion, org.id, denominacion=f"Cliente {i}").codigo for i in range(11)
    ]

    assert codigos == sorted(codigos)


def test_el_correlativo_es_por_organizacion(sesion, org):
    """Si el contador fuera global, el primer cliente de un comercio dependería de otro comercio."""
    propio = service.alta_cliente(sesion, org.id, denominacion="Cliente Propio")

    set_guc(sesion, ORG_GUC, str(org.vecina))
    ajeno = service.alta_cliente(sesion, org.vecina, denominacion="Cliente Vecino")

    assert propio.codigo == "CLI-000001"
    assert ajeno.codigo == "CLI-000001"


def test_el_codigo_generado_no_choca_con_el_importado_de_paradox(sesion, org):
    """El importador entra por `crear_cliente` con el código legacy tal cual (`C001`). Los dos
    caminos comparten `uq_clientes_org_codigo`, así que el prefijo es lo que evita el choque."""
    importado = service.crear_cliente(sesion, org.id, codigo="C001", denominacion="Legacy SA")
    nuevo = service.alta_cliente(sesion, org.id, denominacion="Alta Nueva SA")

    assert importado.codigo == "C001"
    assert nuevo.codigo == "CLI-000001"


def test_el_alta_no_le_pide_codigo_a_quien_llama(sesion, org):
    """Contrato de `alta_cliente`: pasarle un código es un TypeError, no un valor que se ignore."""
    with pytest.raises(TypeError):
        service.alta_cliente(sesion, org.id, denominacion="X", codigo="MIO-1")


# =========================================================================== validación


def test_un_cuit_con_digito_verificador_malo_no_entra(sesion, org):
    with pytest.raises(ValueError, match="CUIT inválido"):
        service.alta_cliente(sesion, org.id, denominacion="Trucho SA", cuit=CUIT_DV_MALO)


def test_un_cuit_valido_entra(sesion, org):
    cliente = service.alta_cliente(sesion, org.id, denominacion="Transporte La Veloz", cuit=CUIT_OK)

    assert cliente.cuit == CUIT_OK


def test_una_condicion_fiscal_inventada_no_entra_ni_por_el_service(sesion, org):
    """La reja va puesta dos veces: el importador NO pasa por el borde HTTP, así que el `Literal`
    de Pydantic no lo alcanza. Sin esto, la basura llegaría al CHECK como IntegrityError ilegible."""
    with pytest.raises(ValueError, match="Condición fiscal inválida"):
        service.alta_cliente(sesion, org.id, denominacion="Rara SA", cond_fiscal="MONOTRIBUTISTA")


def test_las_condiciones_de_python_y_el_check_de_la_base_coinciden(sesion, org):
    """EL CANDADO. `app/core/cond_fiscal.py` y el CHECK de la 0013 son dos copias de la misma lista.
    Si alguien agrega un valor en Python y se olvida de la migración, esto se pone rojo acá y no en
    producción."""
    for condicion in sorted(CONDICIONES_FISCALES):
        cliente = service.alta_cliente(
            sesion, org.id, denominacion=f"Cliente {condicion}", cond_fiscal=condicion
        )
        sesion.flush()  # el CHECK se evalúa acá, no en el commit

        assert cliente.cond_fiscal == condicion


def test_un_cliente_nace_como_consumidor_final_y_activo(sesion, org):
    """El que compra sin identificarse es consumidor final: es la opción más restrictiva."""
    cliente = service.alta_cliente(sesion, org.id, denominacion="Mostrador")

    assert cliente.cond_fiscal == "CONSUMIDOR_FINAL"
    assert cliente.activo is True
    assert cliente.limite_cta_cte == Decimal("0")


def test_la_org_vecina_no_ve_al_cliente(sesion, org):
    service.alta_cliente(sesion, org.id, denominacion="No Se Ve SA")
    sesion.flush()

    set_guc(sesion, ORG_GUC, str(org.vecina))

    assert service.listar_clientes(sesion, org.vecina) == []


# =========================================================================== HTTP (contrato)


@pytest.fixture
def cliente_http(org, monkeypatch):
    monkeypatch.setattr(core_db, "SessionLocal", lambda: Session(create_engine(APP_URL)))
    s = get_settings()
    token = jwt.encode(
        {
            "sub": str(org.user),
            "aud": s.supabase_jwt_audience,
            "exp": datetime.now(UTC) + timedelta(hours=1),
        },
        s.supabase_jwt_secret,
        algorithm="HS256",
    )
    with TestClient(app) as c:
        c.headers.update({"Authorization": f"Bearer {token}"})
        yield c


def test_endpoint_da_de_alta_y_devuelve_el_codigo(cliente_http):
    """Este SÍ commitea (lo hace `get_tenant`), así que no afirma el número absoluto."""
    r = cliente_http.post("/clientes", json={"denominacion": "Gomería Norte"})
    assert r.status_code == 201, r.text
    body = r.json()

    assert body["codigo"].startswith("CLI-")
    assert len(body["codigo"]) == len("CLI-000001")
    assert body["denominacion"] == "Gomería Norte"
    assert body["activo"] is True
    # Plata como STRING, nunca float: la regla no negociable llegando al JSON.
    assert isinstance(body["limite_cta_cte"], str)


def test_endpoint_numera_de_a_uno(cliente_http):
    primero = cliente_http.post("/clientes", json={"denominacion": "Uno"}).json()["codigo"]
    segundo = cliente_http.post("/clientes", json={"denominacion": "Dos"}).json()["codigo"]

    assert int(segundo.removeprefix("CLI-")) == int(primero.removeprefix("CLI-")) + 1


def test_el_cliente_dado_de_alta_aparece_en_el_listado(cliente_http):
    codigo = cliente_http.post("/clientes", json={"denominacion": "Rectificadora"}).json()["codigo"]

    listado = cliente_http.get("/clientes?limite=200").json()

    assert codigo in [c["codigo"] for c in listado]


def test_endpoint_rechaza_el_codigo_en_el_body(cliente_http):
    """El código es del servidor. Si el body lo trae, se ignora — nunca se respeta en silencio."""
    r = cliente_http.post("/clientes", json={"denominacion": "Colada", "codigo": "MIO-1"})

    assert r.status_code == 201, r.text
    assert r.json()["codigo"] != "MIO-1"


def test_endpoint_rechaza_un_cuit_con_dv_malo(cliente_http):
    r = cliente_http.post("/clientes", json={"denominacion": "Trucho SA", "cuit": CUIT_DV_MALO})

    assert r.status_code == 422
    assert "CUIT" in r.json()["detail"]


def test_endpoint_rechaza_una_condicion_fiscal_inventada(cliente_http):
    """La corta Pydantic con el `Literal`, antes de llegar al service."""
    r = cliente_http.post(
        "/clientes", json={"denominacion": "Rara SA", "cond_fiscal": "MONOTRIBUTISTA"}
    )

    assert r.status_code == 422


def test_endpoint_rechaza_una_denominacion_vacia(cliente_http):
    r = cliente_http.post("/clientes", json={"denominacion": ""})

    assert r.status_code == 422


def test_endpoint_rechaza_un_texto_mas_largo_que_la_columna(cliente_http):
    """Sin `max_length` en el schema esto llegaría a Postgres y volvería como 500 (DataError)."""
    r = cliente_http.post("/clientes", json={"denominacion": "X" * 141})

    assert r.status_code == 422


def test_endpoint_rechaza_un_limite_de_credito_negativo(cliente_http):
    r = cliente_http.post("/clientes", json={"denominacion": "Deudora SA", "limite_cta_cte": "-1"})

    assert r.status_code == 422
