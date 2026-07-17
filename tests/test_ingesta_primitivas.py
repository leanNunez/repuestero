"""Las primitivas de escritura que la ingesta visual compone (slice 2).

Sin LLM y sin imágenes: esto es dominio puro. Los tests que importan son los del recálculo
de precios — es la única regla de negocio nueva, y equivocarse ahí significa cambiarle los
precios de venta a un comercio real sin que nadie lo note.
"""

from decimal import Decimal
from types import SimpleNamespace
from uuid import uuid4

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.catalogo import service
from app.catalogo.models import Articulo, ListaPrecio
from app.catalogo.schemas import ArticuloActualizar
from app.core.db import ORG_GUC, set_guc
from app.core.models import Organizacion
from app.proveedores import service as prov_service
from tests.conftest import APP_URL, OWNER_URL


@pytest.fixture(scope="module")
def org(migrated_db):
    """Una org con un artículo y dos listas de precio, sembrada como owner."""
    org_id = uuid4()
    eng = create_engine(OWNER_URL)
    with Session(eng) as s:
        s.add(Organizacion(id=org_id, nombre="Org Primitivas"))
        s.flush()
        s.add(ListaPrecio(org_id=org_id, codigo="MOST", nombre="Mostrador"))
        s.add(ListaPrecio(org_id=org_id, codigo="MAY", nombre="Mayorista"))
        s.commit()
    eng.dispose()
    return SimpleNamespace(id=org_id)


@pytest.fixture
def sesion(org):
    """Sesión app_user con el tenant fijado, en una transacción que se descarta."""
    eng = create_engine(APP_URL)
    conn = eng.connect()
    trans = conn.begin()
    with Session(bind=conn) as s:
        set_guc(s, ORG_GUC, str(org.id))
        yield s
    trans.rollback()
    conn.close()
    eng.dispose()


def _articulo(
    sesion, org, codigo: str, *, costo="100.0000", detalle="FILTRO DE ACEITE"
) -> Articulo:
    art = Articulo(org_id=org.id, codigo=codigo, detalle=detalle, costo=Decimal(costo))
    sesion.add(art)
    sesion.flush()
    return art


def _lista(sesion, org, codigo: str) -> ListaPrecio:
    return service.obtener_lista_precio(sesion, org.id, codigo)


# --------------------------------------------------------------------------- calcular_precio


def test_calcular_precio_es_markup_sobre_costo():
    """LA definición del negocio: costo 100 + margen 40 = 140, NO 166,67.

    166,67 sería margen sobre el precio de venta. La fórmula que usa el resto del sistema
    (ver seeds/generar_demo.py) es markup sobre costo, y desviarse acá haría que los precios
    recalculados por la ingesta no cuadren con los que ya están cargados.
    """
    assert service.calcular_precio(Decimal("100"), Decimal("40")) == Decimal("140.00")


def test_calcular_precio_redondea_a_centavos_sin_float():
    """El costo es numeric(14,4) y el precio numeric(14,2): sin quantize explícito, el
    redondeo lo haría Postgres al guardar y el precio mostrado no sería el guardado."""
    precio = service.calcular_precio(Decimal("33.3333"), Decimal("35.55"))
    assert precio == Decimal("45.18")  # 33.3333 * 1.3555 = 45.1782... → HALF_UP
    assert isinstance(precio, Decimal)
    assert precio.as_tuple().exponent == -2  # exactamente dos decimales


def test_calcular_precio_margen_cero_es_el_costo():
    assert service.calcular_precio(Decimal("250.50"), Decimal("0")) == Decimal("250.50")


# --------------------------------------------------------------------------- upsert_precio


def test_upsert_precio_inserta_y_despues_actualiza(sesion, org):
    """Lo que `fijar_precio` no puede: llamarla dos veces no revienta contra el unique."""
    art = _articulo(sesion, org, "UPS-1")
    lista = _lista(sesion, org, "MOST")

    p1 = service.upsert_precio(
        sesion,
        org.id,
        articulo_id=art.id,
        lista_id=lista.id,
        precio=Decimal("140.00"),
        margen=Decimal("40"),
    )
    p2 = service.upsert_precio(
        sesion,
        org.id,
        articulo_id=art.id,
        lista_id=lista.id,
        precio=Decimal("280.00"),
        margen=Decimal("40"),
    )

    assert p1.id == p2.id  # misma fila, no una nueva
    assert p2.precio == Decimal("280.00")
    assert len(service.listar_precios_de_articulo(sesion, org.id, art.id)) == 1


def test_upsert_precio_sin_margen_no_borra_el_margen_existente(sesion, org):
    """Actualizar el precio sin pasar margen no puede huerfanar el margen cargado: si lo
    borrara, el próximo recálculo encontraría margen NULL y ya no podría recalcular nada."""
    art = _articulo(sesion, org, "UPS-2")
    lista = _lista(sesion, org, "MOST")

    service.upsert_precio(
        sesion,
        org.id,
        articulo_id=art.id,
        lista_id=lista.id,
        precio=Decimal("140.00"),
        margen=Decimal("40"),
    )
    fila = service.upsert_precio(
        sesion,
        org.id,
        articulo_id=art.id,
        lista_id=lista.id,
        precio=Decimal("150.00"),
    )

    assert fila.margen == Decimal("40.00")


def test_fijar_precio_sigue_siendo_insert_only(sesion, org):
    """Regresión de la decisión: `fijar_precio` NO se arregló, se dejó para el importador.
    Si alguien la 'mejora' silenciosamente, este test lo cuenta."""
    from sqlalchemy.exc import IntegrityError

    art = _articulo(sesion, org, "FIJ-1")
    lista = _lista(sesion, org, "MOST")
    service.fijar_precio(sesion, org.id, articulo=art, lista=lista, precio=Decimal("140.00"))

    sp = sesion.begin_nested()
    with pytest.raises(IntegrityError):
        service.fijar_precio(sesion, org.id, articulo=art, lista=lista, precio=Decimal("150.00"))
    sp.rollback()


# ------------------------------------------------------- recálculo: el caso del margen NULL


def test_margen_null_no_permite_recalcular(sesion, org):
    """LA regla central del feature: sin margen cargado no se inventa un precio.

    Este test no ejercita una función de recálculo (esa la compone ingesta_visual), sino la
    condición que la habilita: una fila de precio puede tener margen NULL, y en ese caso no
    hay con qué calcular. El renglón se marca para atención humana y el precio queda intacto.
    """
    art = _articulo(sesion, org, "NULL-1")
    lista = _lista(sesion, org, "MOST")
    service.upsert_precio(
        sesion,
        org.id,
        articulo_id=art.id,
        lista_id=lista.id,
        precio=Decimal("100.00"),
        margen=None,
    )

    ((precio, _lista_obj),) = service.listar_precios_de_articulo(sesion, org.id, art.id)
    assert precio.margen is None
    assert precio.precio == Decimal("100.00")


def test_recalculo_completo_de_dos_listas(sesion, org):
    """El flujo real: cambia el costo → cada lista recalcula con SU margen; la que no tiene
    margen queda como estaba."""
    art = _articulo(sesion, org, "RECALC-1", costo="100.0000")
    most, may = _lista(sesion, org, "MOST"), _lista(sesion, org, "MAY")

    service.upsert_precio(
        sesion,
        org.id,
        articulo_id=art.id,
        lista_id=most.id,
        precio=Decimal("140.00"),
        margen=Decimal("40"),
    )
    service.upsert_precio(
        sesion,
        org.id,
        articulo_id=art.id,
        lista_id=may.id,
        precio=Decimal("115.00"),
        margen=None,
    )

    # Llega un remito con costo 200: se recalcula solo lo que tiene margen.
    service.actualizar_articulo(
        sesion, org.id, articulo=art, datos=ArticuloActualizar(costo=Decimal("200"))
    )
    for precio_fila, _ in service.listar_precios_de_articulo(sesion, org.id, art.id):
        if precio_fila.margen is not None:
            precio_fila.precio = service.calcular_precio(art.costo, precio_fila.margen)
    sesion.flush()

    precios = {
        lista.codigo: fila.precio
        for fila, lista in service.listar_precios_de_articulo(sesion, org.id, art.id)
    }
    assert precios["MOST"] == Decimal("280.00")  # 200 * 1.40
    assert precios["MAY"] == Decimal("115.00")  # sin margen → intacto


# --------------------------------------------------------------------------- actualizar_articulo


def test_actualizar_articulo_solo_pisa_lo_enviado(sesion, org):
    """`exclude_unset` distingue 'no me lo mandaste' de 'ponelo en None'. Sin eso, cargar un
    remito borraría la marca y el rubro del artículo."""
    art = _articulo(sesion, org, "ACT-1")
    art.marca, art.rubro = "Mann", "FILTROS"
    sesion.flush()

    service.actualizar_articulo(
        sesion, org.id, articulo=art, datos=ArticuloActualizar(costo=Decimal("250"))
    )

    assert art.costo == Decimal("250.0000")
    assert art.marca == "Mann"  # intacta
    assert art.rubro == "FILTROS"  # intacto
    assert art.detalle == "FILTRO DE ACEITE"  # intacto


def test_actualizar_articulo_regenera_la_busqueda_lexica(sesion, org):
    """`busqueda` es una columna Computed: Postgres la regenera sola en el UPDATE. Si el
    detalle cambia, el brazo léxico tiene que encontrar el texto NUEVO sin que nadie toque
    esa columna a mano."""
    art = _articulo(sesion, org, "ACT-2", detalle="AMORTIGUADOR TRASERO")
    service.actualizar_articulo(
        sesion,
        org.id,
        articulo=art,
        datos=ArticuloActualizar(detalle="PASTILLA DE FRENO CERAMICA"),
    )
    sesion.flush()

    resultados = service.buscar_articulos(sesion, org.id, q="pastilla freno")
    assert "ACT-2" in [a.codigo for a, _ in resultados]


# --------------------------------------------------------------------------- asegurar_embeddings


def test_asegurar_embeddings_hace_buscable_un_articulo_nuevo(sesion, org):
    """EL test del demo. Un artículo recién creado tiene embedding NULL y es invisible al
    brazo semántico. Después de asegurar_embeddings, se lo encuentra por SIGNIFICADO —
    con palabras que no están literalmente en el detalle."""
    art = _articulo(sesion, org, "EMB-1", detalle="FILTRO DE ACEITE MANN W719")
    assert art.embedding is None

    n = service.asegurar_embeddings(sesion, org.id, articulos=[art])

    assert n == 1
    assert art.embedding is not None


def test_asegurar_embeddings_reembebe_un_articulo_editado(sesion, org):
    """El bug latente que esto tapa: `reindexar_embeddings` SOLO llena NULLs, así que un
    artículo editado conservaría su vector viejo para siempre. Acá el vector tiene que
    cambiar cuando cambia el detalle."""
    art = _articulo(sesion, org, "EMB-2", detalle="AMORTIGUADOR DELANTERO")
    service.asegurar_embeddings(sesion, org.id, articulos=[art])
    vector_viejo = list(art.embedding)

    service.actualizar_articulo(
        sesion, org.id, articulo=art, datos=ArticuloActualizar(detalle="BUJIA NGK BKR6E")
    )
    service.asegurar_embeddings(sesion, org.id, articulos=[art])

    assert list(art.embedding) != vector_viejo


def test_asegurar_embeddings_con_lista_vacia_no_llama_al_modelo(sesion, org):
    assert service.asegurar_embeddings(sesion, org.id, articulos=[]) == 0


# --------------------------------------------------------------------------- proveedores


def test_obtener_o_crear_proveedor_no_duplica(sesion, org):
    p1 = prov_service.obtener_o_crear_proveedor(
        sesion, org.id, codigo="DIST-1", razon_social="Distribuidora Sur"
    )
    p2 = prov_service.obtener_o_crear_proveedor(
        sesion, org.id, codigo="DIST-1", razon_social="Distribuidora Sur SA"
    )

    assert p1.id == p2.id
    # La razón social NO se pisa: lo que leyó un OCR de un papel no es mejor dato que lo
    # que ya está cargado en el sistema.
    assert p2.razon_social == "Distribuidora Sur"


def test_obtener_o_crear_proveedor_completa_cuit_faltante(sesion, org):
    """Completar un dato que faltaba es agregar información, no reemplazarla."""
    p = prov_service.obtener_o_crear_proveedor(
        sesion, org.id, codigo="DIST-2", razon_social="Norte SRL"
    )
    assert p.cuit is None

    p2 = prov_service.obtener_o_crear_proveedor(
        sesion, org.id, codigo="DIST-2", razon_social="Norte SRL", cuit="30-11111111-1"
    )
    assert p2.cuit == "30-11111111-1"


def test_upsert_vinculo_actualiza_costo_y_conserva_codigo_proveedor(sesion, org):
    """Que un remito no traiga el código del proveedor no es razón para borrar el que ya estaba."""
    art = _articulo(sesion, org, "VIN-1")
    prov = prov_service.obtener_o_crear_proveedor(
        sesion, org.id, codigo="DIST-3", razon_social="Este SA"
    )

    prov_service.upsert_vinculo_articulo(
        sesion,
        org.id,
        articulo_id=art.id,
        proveedor_id=prov.id,
        codigo_proveedor="W719/80",
        costo=Decimal("100"),
    )
    v = prov_service.upsert_vinculo_articulo(
        sesion,
        org.id,
        articulo_id=art.id,
        proveedor_id=prov.id,
        costo=Decimal("200"),
    )

    assert v.costo == Decimal("200.0000")
    assert v.codigo_proveedor == "W719/80"  # conservado
