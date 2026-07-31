"""Alta de artículos desde la app: normalización, rejas de negocio, precio opcional y embedding.

Patrón A (service contra Postgres con `app_user`, en transacción que hace rollback). Archivo
propio y no dentro de `test_catalogo.py` a propósito: aquella fixture es `scope="module"`,
commitea 5 artículos y varios de sus tests afirman conteos ABSOLUTOS (`total == 5`). Un alta que
commitee ahí adentro los rompe de costado.

OJO: estos tests ejercen `asegurar_embeddings` con el modelo REAL, sin mock. Correr este archivo
aislado en una máquina limpia baja el modelo de fastembed (~120MB); se cachea para las
siguientes. Es deliberado: mockear `embed_passages` haría pasar el test que afirma
`embedding is not None` mientras el artículo sale invisible a la búsqueda semántica en
producción, que es exactamente el bug que este alta existe para no cometer.
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

from app.catalogo import service
from app.catalogo.models import ListaPrecio
from app.catalogo.schemas import ArticuloCrear
from app.core import db as core_db
from app.core.config import get_settings
from app.core.db import ORG_GUC, set_guc
from app.core.models import Miembro, Organizacion
from app.main import app
from tests.conftest import APP_URL, OWNER_URL


@pytest.fixture(scope="module")
def org(migrated_db):
    """Org vacía con una lista de precios, más una vecina con la suya (para el cruce de listas)."""
    org_id, vecina_id = uuid4(), uuid4()
    eng = create_engine(OWNER_URL)
    with Session(eng) as s:
        s.add(Organizacion(id=org_id, nombre="Org Alta Articulos"))
        s.add(Organizacion(id=vecina_id, nombre="Org Vecina Alta"))
        s.flush()
        propia = ListaPrecio(org_id=org_id, codigo="MOST", nombre="Mostrador")
        ajena = ListaPrecio(org_id=vecina_id, codigo="MOST", nombre="Mostrador de la vecina")
        s.add(propia)
        s.add(ajena)
        s.flush()
        ids = SimpleNamespace(id=org_id, vecina=vecina_id, lista=propia.id, lista_ajena=ajena.id)
        s.commit()
    eng.dispose()
    return ids


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


def _datos(**overrides) -> ArticuloCrear:
    base = {"codigo": "MAH-OC90", "detalle": "FILTRO DE ACEITE MAHLE"}
    return ArticuloCrear(**{**base, **overrides})


# =========================================================================== normalización
def test_recorta_los_espacios_de_todos_los_campos_de_texto(sesion, org):
    articulo, _ = service.alta_articulo(
        sesion,
        org.id,
        datos=_datos(
            codigo="  MAH-OC90  ",
            detalle="  FILTRO DE ACEITE  ",
            marca="  Mahle  ",
            rubro="  FILTROS  ",
            codigo_barra="  7791234567890  ",
        ),
    )
    assert articulo.codigo == "MAH-OC90"
    assert articulo.detalle == "FILTRO DE ACEITE"
    assert articulo.marca == "Mahle"
    assert articulo.rubro == "FILTROS"
    assert articulo.codigo_barra == "7791234567890"


def test_un_codigo_con_espacio_al_final_no_burla_el_unique(sesion, org):
    """Sin el strip, "MAH-OC90 " entra al lado de "MAH-OC90" y el unique no se entera."""
    service.alta_articulo(sesion, org.id, datos=_datos(codigo="MAH-OC90"))
    with pytest.raises(Exception) as exc:  # noqa: B017 — IntegrityError, lo traduce el router
        service.alta_articulo(sesion, org.id, datos=_datos(codigo="  MAH-OC90  "))
    assert "uq_articulos_org_codigo" in str(exc.value)


def test_los_opcionales_vacios_quedan_en_null_no_en_string_vacio(sesion, org):
    """Un "" rompe el `is_not(None)` con el que se arman los dropdowns de rubro y marca."""
    articulo, _ = service.alta_articulo(
        sesion, org.id, datos=_datos(marca="   ", rubro="", codigo_barra="  ")
    )
    assert articulo.marca is None
    assert articulo.rubro is None
    assert articulo.codigo_barra is None


def test_el_case_no_se_toca(sesion, org):
    """Decisión explícita: normalizar solo lo nuevo haría convivir FILTROS con Filtros, que es
    el problema que dice prevenir. Contra los duplicados por case juega la UI, no un .upper()."""
    articulo, _ = service.alta_articulo(
        sesion, org.id, datos=_datos(marca="MANN-FILTER", rubro="Filtros de aceite")
    )
    assert articulo.marca == "MANN-FILTER"
    assert articulo.rubro == "Filtros de aceite"


# =========================================================================== rejas de negocio
@pytest.mark.parametrize("codigo", ["", "   "])
def test_codigo_vacio_post_strip_no_pasa(sesion, org, codigo):
    """ "   " tiene largo 3: un min_length de Pydantic corre ANTES del strip y lo dejaría pasar."""
    with pytest.raises(ValueError, match="código"):
        service.alta_articulo(sesion, org.id, datos=_datos(codigo=codigo))


def test_detalle_vacio_post_strip_no_pasa(sesion, org):
    with pytest.raises(ValueError, match="detalle"):
        service.alta_articulo(sesion, org.id, datos=_datos(detalle="   "))


def test_costo_negativo_no_pasa(sesion, org):
    with pytest.raises(ValueError, match="costo"):
        service.alta_articulo(sesion, org.id, datos=_datos(costo=Decimal("-1")))


def test_costo_dolar_negativo_no_pasa(sesion, org):
    with pytest.raises(ValueError, match="dólares"):
        service.alta_articulo(sesion, org.id, datos=_datos(costo_dolar=Decimal("-0.01")))


@pytest.mark.parametrize("alicuota", [Decimal("-1"), Decimal("101")])
def test_alicuota_fuera_de_rango_no_pasa(sesion, org, alicuota):
    with pytest.raises(ValueError, match="alícuota"):
        service.alta_articulo(sesion, org.id, datos=_datos(alicuota_iva=alicuota))


def test_punto_pedido_negativo_no_pasa(sesion, org):
    with pytest.raises(ValueError, match="punto de pedido"):
        service.alta_articulo(sesion, org.id, datos=_datos(punto_pedido=Decimal("-5")))


# =========================================================================== precio y lista
def test_precio_sin_lista_no_pasa(sesion, org):
    """No hay lista por defecto a nivel sistema: elegir una en silencio sería inventar el
    precio de venta de un artículo."""
    with pytest.raises(ValueError, match="lista de precios"):
        service.alta_articulo(sesion, org.id, datos=_datos(), precio=Decimal("15400"))


@pytest.mark.parametrize("precio", [Decimal("0"), Decimal("-100")])
def test_precio_no_positivo_no_pasa(sesion, org, precio):
    with pytest.raises(ValueError, match="mayor que cero"):
        service.alta_articulo(sesion, org.id, datos=_datos(), precio=precio, lista_id=org.lista)


def test_la_lista_de_otra_org_no_existe_para_mi(sesion, org):
    """RLS hace indistinguible "no existe" de "no es tuya", y el mensaje no filtra cuál es."""
    with pytest.raises(ValueError, match="No existe esa lista"):
        service.alta_articulo(
            sesion, org.id, datos=_datos(), precio=Decimal("100"), lista_id=org.lista_ajena
        )


def test_una_lista_inexistente_no_pasa(sesion, org):
    with pytest.raises(ValueError, match="No existe esa lista"):
        service.alta_articulo(
            sesion, org.id, datos=_datos(), precio=Decimal("100"), lista_id=999_999
        )


def test_con_precio_queda_fijado_en_la_lista_elegida_y_sin_margen(sesion, org):
    articulo, advertencias = service.alta_articulo(
        sesion, org.id, datos=_datos(), precio=Decimal("15400"), lista_id=org.lista
    )
    fila = service.precio_de_articulo(sesion, org.id, articulo_id=articulo.id, lista_id=org.lista)
    assert fila is not None
    assert fila.precio == Decimal("15400.00")
    # Sin margen el precio no se repricea solo cuando entre el próximo remito. Es la falla segura.
    assert fila.margen is None
    assert advertencias == []


def test_sin_precio_se_crea_igual_y_avisa(sesion, org):
    articulo, advertencias = service.alta_articulo(sesion, org.id, datos=_datos())
    assert articulo.id is not None
    assert service.listar_precios_de_articulo(sesion, org.id, articulo.id) == []
    assert len(advertencias) == 1
    assert "SIN precio de venta" in advertencias[0]


def test_una_lista_sin_precio_se_ignora_no_rompe(sesion, org):
    """El `<select>` del front siempre tiene un valor: mandar lista sin precio es un default de
    UI, no un error del usuario."""
    articulo, advertencias = service.alta_articulo(
        sesion, org.id, datos=_datos(), lista_id=org.lista
    )
    assert service.listar_precios_de_articulo(sesion, org.id, articulo.id) == []
    assert len(advertencias) == 1


# =========================================================================== embedding
def test_el_articulo_nace_buscable_por_significado(sesion, org):
    """LA razón por la que este alta no es copiar el patrón de `alta_cliente`.

    El brazo vectorial de la búsqueda filtra `embedding is not null`. Sin este paso el artículo
    queda invisible a la búsqueda semántica hasta que corra un batch, y quien lo carga y lo
    busca a los diez segundos no lo encuentra.
    """
    articulo, _ = service.alta_articulo(sesion, org.id, datos=_datos())
    assert articulo.embedding is not None
    assert len(articulo.embedding) > 0


# =========================================================================== escalas de la base
def test_la_plata_vuelve_con_la_escala_de_la_base(sesion, org):
    """Sin el `session.refresh`, el POST devolvería "0" donde el GET devuelve "0.0000": el mismo
    campo del mismo registro con dos representaciones según por dónde se lo pida."""
    articulo, _ = service.alta_articulo(
        sesion,
        org.id,
        datos=_datos(costo=Decimal("1234.5"), costo_dolar=Decimal("10"), punto_pedido=Decimal("3")),
    )
    assert articulo.costo.as_tuple().exponent == -4  # numeric(14,4)
    assert articulo.costo_dolar.as_tuple().exponent == -4
    assert articulo.alicuota_iva.as_tuple().exponent == -2  # numeric(5,2)
    assert articulo.punto_pedido.as_tuple().exponent == -2  # numeric(14,2)
    assert str(articulo.alicuota_iva) == "21.00"  # el default, con la escala de la columna


# =========================================================================== multi-tenant
def test_la_org_vecina_no_ve_el_articulo(sesion, org):
    articulo, _ = service.alta_articulo(sesion, org.id, datos=_datos())
    assert service.obtener_articulo(sesion, org.id, articulo.codigo) is not None

    set_guc(sesion, ORG_GUC, str(org.vecina))
    assert service.obtener_articulo(sesion, org.vecina, articulo.codigo) is None


# =========================================================================== HTTP (contrato)
@pytest.fixture(scope="module")
def org_http(migrated_db):
    """Org con miembro (sin esto `get_tenant` da 403), su lista y una lista de la vecina."""
    org_id, vecina_id, user_id = uuid4(), uuid4(), uuid4()
    eng = create_engine(OWNER_URL)
    with Session(eng) as s:
        s.add(Organizacion(id=org_id, nombre="Org Alta HTTP"))
        s.add(Organizacion(id=vecina_id, nombre="Org Vecina Alta HTTP"))
        s.flush()
        propia = ListaPrecio(org_id=org_id, codigo="MOST", nombre="Mostrador")
        ajena = ListaPrecio(org_id=vecina_id, codigo="MOST", nombre="Mostrador vecino")
        s.add(propia)
        s.add(ajena)
        s.add(Miembro(org_id=org_id, user_id=user_id, rol="admin"))
        s.flush()
        ids = SimpleNamespace(id=org_id, user=user_id, lista=propia.id, lista_ajena=ajena.id)
        s.commit()
    eng.dispose()
    return ids


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


def _payload(**overrides) -> dict:
    """Estos tests COMMITEAN (lo hace `get_tenant`), así que cada uno usa un código único: sin
    eso el segundo que corriera chocaría contra el unique del primero."""
    base = {"codigo": f"HTTP-{uuid4().hex[:8]}", "detalle": "FILTRO DE ACEITE HTTP"}
    return {**base, **overrides}


def test_alta_devuelve_201_con_el_articulo_y_las_advertencias(cliente):
    r = cliente.post("/catalogo/articulos", json=_payload())
    assert r.status_code == 201
    body = r.json()
    assert set(body) == {"articulo", "advertencias"}
    assert body["articulo"]["detalle"] == "FILTRO DE ACEITE HTTP"
    assert body["articulo"]["activo"] is True


def test_el_codigo_repetido_da_409(cliente):
    payload = _payload()
    assert cliente.post("/catalogo/articulos", json=payload).status_code == 201
    r = cliente.post("/catalogo/articulos", json=payload)
    assert r.status_code == 409
    assert "ya existe" in r.json()["detail"].lower()


def test_codigo_vacio_da_422(cliente):
    r = cliente.post("/catalogo/articulos", json=_payload(codigo="   "))
    assert r.status_code == 422


def test_precio_sin_lista_da_422(cliente):
    r = cliente.post("/catalogo/articulos", json=_payload(precio="15400"))
    assert r.status_code == 422
    assert "lista de precios" in r.json()["detail"]


def test_la_lista_de_otra_org_da_422(cliente, org_http):
    r = cliente.post(
        "/catalogo/articulos",
        json=_payload(precio="15400", lista_id=org_http.lista_ajena),
    )
    assert r.status_code == 422
    assert "No existe esa lista" in r.json()["detail"]


def test_sin_precio_avisa_en_la_respuesta(cliente):
    body = cliente.post("/catalogo/articulos", json=_payload()).json()
    assert len(body["advertencias"]) == 1
    assert "SIN precio de venta" in body["advertencias"][0]


def test_con_precio_no_hay_advertencias(cliente, org_http):
    body = cliente.post(
        "/catalogo/articulos",
        json=_payload(precio="15400", lista_id=org_http.lista),
    ).json()
    assert body["advertencias"] == []


def test_la_plata_viaja_como_string_nunca_como_float(cliente):
    body = cliente.post("/catalogo/articulos", json=_payload(costo="1234.50")).json()
    assert isinstance(body["articulo"]["costo"], str)
    assert body["articulo"]["costo"] == "1234.5000"  # la escala de numeric(14,4)


def test_el_articulo_recien_creado_se_encuentra_en_el_listado_y_en_la_busqueda(cliente):
    """El circuito completo por HTTP: doy de alta y lo encuentro por los dos caminos.

    OJO con lo que este test NO prueba: verificado por mutación, sigue pasando con
    `asegurar_embeddings` comentada. La búsqueda híbrida tiene un brazo léxico sobre la columna
    `busqueda`, que Postgres genera sola en el INSERT, así que el artículo aparece igual aunque
    el vector nunca se haya calculado. El guardián del embedding es
    `test_el_articulo_nace_buscable_por_significado`, que mira la columna directamente.
    """
    payload = _payload(codigo=f"ZZ-{uuid4().hex[:8]}", detalle="AMORTIGUADOR TRASERO SACHS")
    assert cliente.post("/catalogo/articulos", json=payload).status_code == 201

    listado = cliente.get(f"/catalogo/articulos?buscar={payload['codigo']}").json()
    assert [a["codigo"] for a in listado["items"]] == [payload["codigo"]]

    encontrados = cliente.get("/catalogo/buscar?q=amortiguador+sachs").json()
    assert payload["codigo"] in [a["codigo"] for a in encontrados]
