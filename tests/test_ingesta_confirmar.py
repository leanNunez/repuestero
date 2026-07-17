"""La escritura (slice 5). El único camino de la feature que toca la base.

Todo contra Postgres real, sin LLM: confirmar no llama al modelo — recibe lo que el humano
aprobó. Los tests que no pueden faltar son cuatro: la regla del margen NULL, la idempotencia,
la atomicidad y el embedding (sin ese último, el demo se pincha en cámara).
"""

from decimal import Decimal
from types import SimpleNamespace
from uuid import uuid4

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.catalogo import service as catalogo
from app.catalogo.models import Articulo, ListaPrecio
from app.core.db import ORG_GUC, set_guc
from app.core.models import Organizacion
from app.ingesta_visual import service
from app.ingesta_visual.schemas import ConfirmarRequest, RenglonConfirmar
from app.inventario import service as inventario
from tests.conftest import APP_URL, OWNER_URL

USUARIO = uuid4()


@pytest.fixture(scope="module")
def org(migrated_db):
    """Org con depósito, dos listas y un artículo existente con margen cargado."""
    org_id = uuid4()
    eng = create_engine(OWNER_URL)
    with Session(eng) as s:
        s.add(Organizacion(id=org_id, nombre="Org Confirmar"))
        s.flush()
        inventario.crear_deposito(s, org_id, codigo="CEN", nombre="Central")
        most = ListaPrecio(org_id=org_id, codigo="MOST", nombre="Mostrador")
        may = ListaPrecio(org_id=org_id, codigo="MAY", nombre="Mayorista")
        s.add_all([most, may])
        art = Articulo(
            org_id=org_id,
            codigo="W719/80",
            detalle="FILTRO DE ACEITE MANN W719/80",
            costo=Decimal("100"),
        )
        s.add(art)
        s.flush()
        # MOST con margen 40 → se recalcula. MAY SIN margen → NO se toca.
        catalogo.upsert_precio(
            s,
            org_id,
            articulo_id=art.id,
            lista_id=most.id,
            precio=Decimal("140.00"),
            margen=Decimal("40"),
        )
        catalogo.upsert_precio(
            s, org_id, articulo_id=art.id, lista_id=may.id, precio=Decimal("115.00"), margen=None
        )
        s.commit()
    eng.dispose()
    return SimpleNamespace(id=org_id)


@pytest.fixture
def sesion(org):
    eng = create_engine(APP_URL)
    conn = eng.connect()
    trans = conn.begin()
    with Session(bind=conn) as s:
        set_guc(s, ORG_GUC, str(org.id))
        yield s
    trans.rollback()
    conn.close()
    eng.dispose()


def _req(renglones, *, hash_="a" * 64, deposito="CEN", **kw):
    return ConfirmarRequest(remito_hash=hash_, deposito_codigo=deposito, renglones=renglones, **kw)


def _renglon(codigo="NUEVO-1", detalle="BUJIA NGK BKR6E", cant="5", costo="4200", **kw):
    return RenglonConfirmar(
        codigo=codigo, detalle=detalle, cantidad=Decimal(cant), costo_unitario=Decimal(costo), **kw
    )


def _stock(sesion, org, codigo) -> Decimal:
    """Lee la VISTA stock, nunca un número guardado."""
    return sesion.execute(
        text(
            "select s.cantidad from stock s join articulos a on a.id = s.articulo_id "
            "where a.codigo = :c"
        ),
        {"c": codigo},
    ).scalar()


# =========================================================== alta


def test_alta_crea_articulo_stock_y_embedding(sesion, org):
    """EL test del demo: después de confirmar, el artículo existe, tiene stock y es
    buscable por SIGNIFICADO. Sin el embedding, cargás el producto en cámara, se lo
    preguntás a Repu y no lo encuentra."""
    r = service.confirmar(sesion, org.id, datos=_req([_renglon()]), usuario_id=USUARIO)

    assert r.articulos_creados == ["NUEVO-1"]
    assert r.movimientos == 1

    art = catalogo.obtener_articulo(sesion, org.id, "NUEVO-1")
    assert art.costo == Decimal("4200.0000")
    assert _stock(sesion, org, "NUEVO-1") == Decimal("5.00")
    assert art.embedding is not None  # ← sin esto el demo se pincha


def test_alta_avisa_que_queda_sin_precio(sesion, org):
    """No se inventa un margen para un artículo nuevo. Se crea sin precio y se avisa."""
    r = service.confirmar(sesion, org.id, datos=_req([_renglon(codigo="NUEVO-2")]))

    assert (
        catalogo.listar_precios_de_articulo(
            sesion, org.id, catalogo.obtener_articulo(sesion, org.id, "NUEVO-2").id
        )
        == []
    )
    assert any("SIN precio de venta" in a for a in r.advertencias)


# =========================================================== actualización + recálculo


def test_actualiza_costo_y_recalcula_solo_las_listas_con_margen(sesion, org):
    """La regla central del feature, de punta a punta.

    Costo 100 → 200. MOST tiene margen 40 → precio pasa a 280 (markup sobre costo).
    MAY no tiene margen → su precio queda intacto y el código se reporta.
    """
    r = service.confirmar(
        sesion,
        org.id,
        datos=_req([_renglon(codigo="W719/80", detalle="FILTRO", cant="10", costo="200")]),
        usuario_id=USUARIO,
    )

    assert r.articulos_actualizados == ["W719/80"]
    assert r.precios_recalculados == 1
    assert r.renglones_sin_margen == ["W719/80"]

    art = catalogo.obtener_articulo(sesion, org.id, "W719/80")
    assert art.costo == Decimal("200.0000")

    precios = {
        lista.codigo: (fila.precio, fila.margen)
        for fila, lista in catalogo.listar_precios_de_articulo(sesion, org.id, art.id)
    }
    assert precios["MOST"] == (Decimal("280.00"), Decimal("40.00"))  # 200 * 1.40
    assert precios["MAY"] == (Decimal("115.00"), None)  # INTACTO


def test_actualizacion_no_pisa_el_detalle_existente(sesion, org):
    """El detalle que leyó un OCR no es mejor dato que el que ya está cargado. Solo se
    actualiza el costo."""
    service.confirmar(
        sesion,
        org.id,
        datos=_req([_renglon(codigo="W719/80", detalle="filtro mal escaneado", costo="300")]),
    )

    art = catalogo.obtener_articulo(sesion, org.id, "W719/80")
    assert art.detalle == "FILTRO DE ACEITE MANN W719/80"
    assert art.costo == Decimal("300.0000")


def test_sin_margen_reportado_no_es_un_error(sesion, org):
    """Que falte el margen se avisa, pero la carga se completa igual."""
    r = service.confirmar(sesion, org.id, datos=_req([_renglon(codigo="W719/80", costo="200")]))
    assert r.movimientos == 1
    assert any("no tienen margen cargado" in a for a in r.advertencias)


# =========================================================== kardex


def test_el_movimiento_apunta_al_remito_que_lo_originó(sesion, org):
    """`ref_tipo`/`ref_id` son lo que permite contestar 'este stock, ¿de dónde salió?'.
    Por eso el remito se inserta ANTES que los renglones: su id tiene que existir."""
    r = service.confirmar(
        sesion, org.id, datos=_req([_renglon(codigo="REF-1")]), usuario_id=USUARIO
    )

    mov = sesion.execute(
        text(
            "select motivo, ref_tipo, ref_id, creado_por from stock_movimientos where ref_id = :r"
        ),
        {"r": r.remito_id},
    ).one()

    assert mov.motivo == "compra"
    assert mov.ref_tipo == "remito"
    assert mov.creado_por == USUARIO


# =========================================================== idempotencia


def test_el_mismo_remito_no_entra_dos_veces(sesion, org):
    """El candado es el unique index, no un `if`. Dos pestañas apretando Confirmar a la vez
    no pueden duplicar el stock."""
    service.confirmar(sesion, org.id, datos=_req([_renglon(codigo="IDEM-1")], hash_="b" * 64))
    stock_1 = _stock(sesion, org, "IDEM-1")

    sp = sesion.begin_nested()
    with pytest.raises(IntegrityError) as exc:
        service.confirmar(sesion, org.id, datos=_req([_renglon(codigo="IDEM-1")], hash_="b" * 64))
    sp.rollback()

    assert "uq_remitos_org_hash" in str(exc.value)
    assert _stock(sesion, org, "IDEM-1") == stock_1  # NO se duplicó


# =========================================================== atomicidad


def test_un_remito_es_todo_o_nada(sesion, org, monkeypatch):
    """Si un renglón del medio falla, los anteriores NO quedan cargados.

    No existe el remito a medias: sería peor que no cargarlo, porque nadie sabría qué entró
    y qué no. Se fuerza el fallo en el SEGUNDO movimiento de stock, que es lo más tarde que
    puede romperse algo (después de haber creado artículo, vínculo y el remito mismo).
    """
    antes = sesion.execute(text("select count(*) from articulos")).scalar_one()

    real = inventario.registrar_movimiento
    llamadas = {"n": 0}

    def _falla_en_el_segundo(*a, **kw):
        llamadas["n"] += 1
        if llamadas["n"] == 2:
            raise RuntimeError("boom a mitad del remito")
        return real(*a, **kw)

    monkeypatch.setattr(service.inventario, "registrar_movimiento", _falla_en_el_segundo)

    sp = sesion.begin_nested()
    with pytest.raises(RuntimeError, match="boom"):
        service.confirmar(
            sesion,
            org.id,
            datos=_req([_renglon(codigo="ATOM-1"), _renglon(codigo="ATOM-2")], hash_="c" * 64),
        )
    sp.rollback()

    assert sesion.execute(text("select count(*) from articulos")).scalar_one() == antes
    assert catalogo.obtener_articulo(sesion, org.id, "ATOM-1") is None  # el que SÍ se creó
    assert catalogo.obtener_articulo(sesion, org.id, "ATOM-2") is None


def test_codigo_repetido_en_el_remito_suma_las_dos_cantidades(sesion, org):
    """Dos renglones del mismo artículo NO son un error: son dos movimientos de stock reales.

    El primero da de alta el artículo, el segundo lo encuentra (el flush ya lo hizo visible)
    y actualiza. Entran 5 + 5 = 10 unidades, que es lo correcto. `flags.duplicado` lo marca
    en la propuesta para que el humano confirme que el papel realmente dice eso.
    """
    r = service.confirmar(
        sesion,
        org.id,
        datos=_req(
            [
                _renglon(codigo="DUP-1", cant="5", costo="100"),
                _renglon(codigo="DUP-1", cant="5", costo="120"),
            ],
            hash_="9" * 64,
        ),
    )

    assert r.movimientos == 2
    assert _stock(sesion, org, "DUP-1") == Decimal("10.00")
    # El costo queda el del ÚLTIMO renglón: es el que el humano vio más abajo en la lista.
    assert catalogo.obtener_articulo(sesion, org.id, "DUP-1").costo == Decimal("120.0000")


def test_deposito_inexistente_falla_antes_de_escribir_nada(sesion, org):
    """`registrar_movimiento` no valida el depósito (confía en la FK). El chequeo explícito
    da un error entendible en vez de un fallo de FK a mitad de camino."""
    antes = sesion.execute(text("select count(*) from remitos_procesados")).scalar_one()

    with pytest.raises(service.DatoInvalido, match="depósito"):
        service.confirmar(
            sesion, org.id, datos=_req([_renglon(codigo="X-1")], deposito="NO-EXISTE")
        )

    assert sesion.execute(text("select count(*) from remitos_procesados")).scalar_one() == antes


# =========================================================== proveedor y auditoría


def test_vincula_el_articulo_al_proveedor_con_su_codigo(sesion, org):
    """El código con el que el PROVEEDOR llama a la pieza es lo que permite reconocerla en
    el próximo remito."""
    service.confirmar(
        sesion,
        org.id,
        datos=_req(
            [_renglon(codigo="PROV-1", codigo_proveedor="W719/80-MANN")],
            hash_="d" * 64,
            proveedor_codigo="DIST-1",
            proveedor_razon_social="Distribuidora Sur",
        ),
    )

    fila = sesion.execute(
        text(
            "select ap.codigo_proveedor, ap.costo, p.razon_social "
            "from articulo_proveedores ap "
            "join proveedores p on p.id = ap.proveedor_id "
            "join articulos a on a.id = ap.articulo_id where a.codigo = 'PROV-1'"
        )
    ).one()

    assert fila.codigo_proveedor == "W719/80-MANN"
    assert fila.razon_social == "Distribuidora Sur"


def test_guarda_la_propuesta_aprobada_para_auditoria(sesion, org):
    """Dentro de seis meses, '¿quién metió este costo?' se contesta con una fila."""
    r = service.confirmar(
        sesion,
        org.id,
        datos=_req(
            [_renglon(codigo="AUD-1", costo="1234.56")], hash_="e" * 64, numero_remito="R-0001"
        ),
        usuario_id=USUARIO,
    )

    fila = sesion.execute(
        text(
            "select numero_remito, renglones_count, propuesta, creado_por "
            "from remitos_procesados where id = :i"
        ),
        {"i": r.remito_id},
    ).one()

    assert fila.numero_remito == "R-0001"
    assert fila.renglones_count == 1
    assert fila.creado_por == USUARIO
    assert fila.propuesta["renglones"][0]["costo_unitario"] == "1234.56"


def test_sin_proveedor_igual_carga(sesion, org):
    """Un remito sin proveedor identificable no es motivo para no cargar la mercadería."""
    r = service.confirmar(
        sesion, org.id, datos=_req([_renglon(codigo="SINPROV-1")], hash_="f" * 64)
    )
    assert r.movimientos == 1
