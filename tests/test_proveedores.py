"""Alta de proveedores y padrón paginado. Espejo de `test_clientes.py`.

Dos patrones, como el resto de la suite:
- Patrón A (service contra Postgres con `app_user`, en transacción que hace rollback): el número
  exacto SÍ es determinístico.
- Patrón B (TestClient con JWT): el contrato HTTP. Estos COMMITEAN, así que nunca afirman un
  número absoluto.

Lo que no puede faltar:
- Que el código generado NO pise al que trae un remito escaneado. Comparten
  `uq_proveedores_org_codigo`, y el de la ingesta lo eligió un OCR.
- Que un CUIT ilegible de un remito NO frene la ingesta, pero tampoco se guarde.
"""

from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from uuid import uuid4

import jwt
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.core import db as core_db
from app.core.config import get_settings
from app.core.db import ORG_GUC, set_guc
from app.core.models import Miembro, Organizacion
from app.main import app
from app.proveedores import service
from tests.conftest import APP_URL, OWNER_URL

CUIT_OK = "30-71233445-9"
CUIT_DV_MALO = "30-71233445-1"


@pytest.fixture(scope="module")
def org(migrated_db):
    """Org vacía (sin proveedores sembrados) más una vecina, para probar el aislamiento."""
    org_id, vecina_id, user_id = uuid4(), uuid4(), uuid4()
    eng = create_engine(OWNER_URL)
    with Session(eng) as s:
        s.add(Organizacion(id=org_id, nombre="Org Proveedores"))
        s.add(Organizacion(id=vecina_id, nombre="Org Vecina Proveedores"))
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


def test_el_primer_proveedor_de_una_org_arranca_en_uno(sesion, org):
    proveedor = service.alta_proveedor(sesion, org.id, razon_social="Distribuidora Central")

    assert proveedor.codigo == "PRV-000001"


def test_el_codigo_es_correlativo_y_sin_huecos(sesion, org):
    codigos = [
        service.alta_proveedor(sesion, org.id, razon_social=f"Prov {i}").codigo for i in range(3)
    ]

    assert codigos == ["PRV-000001", "PRV-000002", "PRV-000003"]


def test_el_correlativo_es_por_organizacion(sesion, org):
    """Si fuera global, el proveedor 1 de un comercio dependería de cuántos cargó otro."""
    service.alta_proveedor(sesion, org.id, razon_social="De la Org A")
    sesion.flush()

    set_guc(sesion, ORG_GUC, str(org.vecina))
    de_la_vecina = service.alta_proveedor(sesion, org.vecina, razon_social="De la Org B")

    assert de_la_vecina.codigo == "PRV-000001"


def test_el_codigo_generado_no_choca_con_el_que_trae_un_remito(sesion, org):
    """El código de la ingesta lo eligió un OCR leyendo un papel. Sin prefijo, un alta desde la
    app puede chocar contra él y quedar bloqueada sin arreglo posible."""
    service.obtener_o_crear_proveedor(sesion, org.id, codigo="000001", razon_social="Del Remito")
    sesion.flush()

    desde_la_app = service.alta_proveedor(sesion, org.id, razon_social="Desde la App")

    assert desde_la_app.codigo == "PRV-000001"
    assert desde_la_app.codigo != "000001"


def test_el_alta_no_le_pide_codigo_a_quien_llama(sesion, org):
    proveedor = service.alta_proveedor(sesion, org.id, razon_social="Sin Código SA")

    assert proveedor.codigo.startswith("PRV-")
    assert proveedor.activo is True


# =========================================================================== el CUIT


def test_un_cuit_con_digito_verificador_malo_no_entra(sesion, org):
    with pytest.raises(ValueError, match="CUIT inválido"):
        service.alta_proveedor(sesion, org.id, razon_social="Trucho SA", cuit=CUIT_DV_MALO)


def test_un_cuit_valido_entra(sesion, org):
    proveedor = service.alta_proveedor(sesion, org.id, razon_social="Legal SA", cuit=CUIT_OK)

    assert proveedor.cuit == CUIT_OK


def test_el_cuit_tambien_se_valida_por_la_puerta_del_importador(sesion, org):
    """`crear_proveedor` no pasa por FastAPI: si la reja estuviera solo en el borde HTTP, el
    importador de Paradox metería CUITs basura sin que nadie diga nada."""
    with pytest.raises(ValueError, match="CUIT inválido"):
        service.crear_proveedor(
            sesion, org.id, codigo="P001", razon_social="Importado", cuit=CUIT_DV_MALO
        )


def test_un_cuit_ilegible_del_remito_NO_frena_la_ingesta(sesion, org):
    """El dato no lo tipeó nadie: lo leyó un OCR de un papel que puede estar arrugado. Frenar la
    carga entera por un dígito mal leído cambia un campo vacío por un remito que no entra."""
    proveedor = service.obtener_o_crear_proveedor(
        sesion, org.id, codigo="P900", razon_social="Del Remito SA", cuit=CUIT_DV_MALO
    )

    assert proveedor.razon_social == "Del Remito SA"
    # Pero tampoco se guarda: un CUIT a medias parece un dato, y es peor que ninguno.
    assert proveedor.cuit is None


def test_un_cuit_ilegible_no_pisa_al_que_ya_estaba(sesion, org):
    service.crear_proveedor(sesion, org.id, codigo="P901", razon_social="Ya Estaba", cuit=CUIT_OK)

    proveedor = service.obtener_o_crear_proveedor(
        sesion, org.id, codigo="P901", razon_social="Ya Estaba", cuit=CUIT_DV_MALO
    )

    assert proveedor.cuit == CUIT_OK


# =========================================================================== el padrón paginado


def test_la_org_vecina_no_ve_al_proveedor(sesion, org):
    service.alta_proveedor(sesion, org.id, razon_social="No Se Ve SA")
    sesion.flush()

    set_guc(sesion, ORG_GUC, str(org.vecina))

    assert service.listar_proveedores(sesion, org.vecina) == ([], 0)


def test_el_total_es_el_del_resultado_filtrado_y_no_el_del_padron(sesion, org):
    for nombre in ("Distribuidora Sur", "Distribuidora Norte", "Repuestos Ávila"):
        service.alta_proveedor(sesion, org.id, razon_social=nombre)

    items, total = service.listar_proveedores(sesion, org.id, buscar="Distribuidora")

    assert total == 2
    assert [p.razon_social for p in items] == ["Distribuidora Norte", "Distribuidora Sur"]


def test_un_proveedor_del_fondo_del_abecedario_se_encuentra_buscandolo(sesion, org):
    """El bug: con el padrón cortado en los primeros 50 por orden alfabético, la pantalla de
    compras no podía elegir un proveedor que no estuviera en esa tanda."""
    for i in range(60):
        service.alta_proveedor(sesion, org.id, razon_social=f"Proveedor {i:03d}")
    service.alta_proveedor(sesion, org.id, razon_social="Zanella Repuestos")

    primera_pagina, _ = service.listar_proveedores(sesion, org.id, limite=50)
    assert "Zanella Repuestos" not in [p.razon_social for p in primera_pagina]

    encontrado, total = service.listar_proveedores(sesion, org.id, buscar="zanella")
    assert total == 1
    assert encontrado[0].razon_social == "Zanella Repuestos"


def test_se_busca_por_cuit_y_por_codigo(sesion, org):
    codigo = service.alta_proveedor(
        sesion, org.id, razon_social="Bulonera Rosario", cuit=CUIT_OK
    ).codigo
    service.alta_proveedor(sesion, org.id, razon_social="Otra Sin CUIT")

    por_cuit, total_cuit = service.listar_proveedores(sesion, org.id, buscar="71233445")
    por_codigo, total_codigo = service.listar_proveedores(sesion, org.id, buscar=codigo)

    assert total_cuit == 1
    assert por_cuit[0].razon_social == "Bulonera Rosario"
    assert total_codigo == 1
    assert por_codigo[0].codigo == codigo


def test_la_paginacion_no_repite_ni_saltea_con_homonimos(sesion, org):
    for _ in range(4):
        service.alta_proveedor(sesion, org.id, razon_social="Distribuidora Sur")

    primera, total = service.listar_proveedores(sesion, org.id, limite=2, offset=0)
    segunda, _ = service.listar_proveedores(sesion, org.id, limite=2, offset=2)

    assert total == 4
    assert len({p.codigo for p in primera + segunda}) == 4


def test_el_offset_mas_alla_del_total_devuelve_pagina_vacia_pero_el_total_sigue(sesion, org):
    service.alta_proveedor(sesion, org.id, razon_social="Único")

    items, total = service.listar_proveedores(sesion, org.id, limite=50, offset=500)

    assert items == []
    assert total == 1


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
    r = cliente_http.post("/proveedores", json={"razon_social": "Bulonera del Norte"})
    assert r.status_code == 201, r.text
    body = r.json()

    assert body["codigo"].startswith("PRV-")
    assert len(body["codigo"]) == len("PRV-000001")
    assert body["razon_social"] == "Bulonera del Norte"
    assert body["activo"] is True


def test_endpoint_numera_de_a_uno(cliente_http):
    primero = cliente_http.post("/proveedores", json={"razon_social": "Uno"}).json()["codigo"]
    segundo = cliente_http.post("/proveedores", json={"razon_social": "Dos"}).json()["codigo"]

    assert int(segundo.removeprefix("PRV-")) == int(primero.removeprefix("PRV-")) + 1


def test_endpoint_devuelve_items_y_total(cliente_http):
    cliente_http.post("/proveedores", json={"razon_social": "Contrato SA"})

    body = cliente_http.get("/proveedores?limite=1").json()

    assert isinstance(body["items"], list)
    assert len(body["items"]) <= 1
    assert body["total"] >= len(body["items"])


def test_endpoint_encuentra_por_busqueda_al_recien_dado_de_alta(cliente_http):
    codigo = cliente_http.post(
        "/proveedores", json={"razon_social": "Bulonera Insólita del Sur"}
    ).json()["codigo"]

    body = cliente_http.get("/proveedores?buscar=Insólita").json()

    assert body["total"] == 1
    assert body["items"][0]["codigo"] == codigo


def test_endpoint_rechaza_el_codigo_en_el_body(cliente_http):
    """El código es del servidor. Si el body lo trae, se ignora — nunca se respeta en silencio."""
    r = cliente_http.post(
        "/proveedores", json={"razon_social": "Con Código", "codigo": "ELEGIDO-POR-MI"}
    )

    assert r.status_code == 201, r.text
    assert r.json()["codigo"] != "ELEGIDO-POR-MI"
    assert r.json()["codigo"].startswith("PRV-")


def test_endpoint_rechaza_un_cuit_con_dv_malo(cliente_http):
    r = cliente_http.post("/proveedores", json={"razon_social": "Trucho SA", "cuit": CUIT_DV_MALO})

    assert r.status_code == 422
    assert "CUIT" in r.json()["detail"]


def test_endpoint_rechaza_una_razon_social_vacia(cliente_http):
    assert cliente_http.post("/proveedores", json={"razon_social": ""}).status_code == 422


def test_endpoint_rechaza_un_texto_mas_largo_que_la_columna(cliente_http):
    r = cliente_http.post("/proveedores", json={"razon_social": "x" * 121})

    assert r.status_code == 422


def test_endpoint_rechaza_un_offset_negativo(cliente_http):
    assert cliente_http.get("/proveedores?offset=-1").status_code == 422
