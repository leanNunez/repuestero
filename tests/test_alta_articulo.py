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

from decimal import Decimal
from types import SimpleNamespace
from uuid import uuid4

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.catalogo import service
from app.catalogo.models import ListaPrecio
from app.catalogo.schemas import ArticuloCrear
from app.core.db import ORG_GUC, set_guc
from app.core.models import Organizacion
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
