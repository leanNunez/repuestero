"""Compras (Fase 2, slice 3). Todo contra Postgres real, sin LLM.

Los que no pueden faltar: el IVA por renglón, que la compra SUMA stock, que actualiza el costo
(último pisa) y repricea las listas con margen (y NO las sin margen), la cta cte de proveedor
(Debe por compra a crédito, Haber por pago), el unique de factura, el append-only y el RLS.
"""

from decimal import Decimal
from types import SimpleNamespace
from uuid import uuid4

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.catalogo import service as catalogo
from app.catalogo.models import Articulo
from app.catalogo.schemas import ListaPrecioCrear
from app.compras import service
from app.compras.schemas import CompraCrear, RenglonCompraCrear
from app.core.db import ORG_GUC, set_guc
from app.core.models import Organizacion
from app.inventario import service as inventario
from app.proveedores import service as proveedores
from tests.conftest import APP_URL, OWNER_URL

USUARIO = uuid4()


@pytest.fixture(scope="module")
def org(migrated_db):
    """Org con depósito, un proveedor, y dos artículos con 10 de stock. BUJIA-1 tiene dos listas:
    MOST con margen 50 (se repricea) y SIN sin margen (no se toca)."""
    org_id = uuid4()
    eng = create_engine(OWNER_URL)
    with Session(eng) as s:
        s.add(Organizacion(id=org_id, nombre="Org Compras"))
        s.flush()
        dep = inventario.crear_deposito(s, org_id, codigo="CEN", nombre="Central")
        proveedores.crear_proveedor(s, org_id, codigo="PROV-1", razon_social="Proveedor Uno")
        arts = {}
        for codigo, detalle in (("BUJIA-1", "BUJIA NGK BKR6E"), ("FILTRO-1", "FILTRO ACEITE")):
            art = Articulo(
                org_id=org_id,
                codigo=codigo,
                detalle=detalle,
                costo=Decimal("100"),
                alicuota_iva=Decimal("21.00"),
            )
            s.add(art)
            s.flush()
            arts[codigo] = art
            inventario.registrar_movimiento(
                s,
                org_id,
                articulo_id=art.id,
                deposito_id=dep.id,
                cantidad=Decimal("10"),
                motivo="inicial",
            )
        most = catalogo.crear_lista_precio(
            s, org_id, ListaPrecioCrear(codigo="MOST", nombre="Mostrador")
        )
        sin = catalogo.crear_lista_precio(
            s, org_id, ListaPrecioCrear(codigo="SIN", nombre="Sin margen")
        )
        catalogo.upsert_precio(
            s,
            org_id,
            articulo_id=arts["BUJIA-1"].id,
            lista_id=most.id,
            precio=Decimal("150"),
            margen=Decimal("50"),
        )
        catalogo.upsert_precio(
            s,
            org_id,
            articulo_id=arts["BUJIA-1"].id,
            lista_id=sin.id,
            precio=Decimal("999"),
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


def _compra(*, cantidad="1", costo="200", codigo="BUJIA-1", numero="A-0001", **kw) -> CompraCrear:
    return CompraCrear(
        proveedor_codigo="PROV-1",
        deposito_codigo="CEN",
        numero_comprobante=numero,
        renglones=[
            RenglonCompraCrear(
                articulo_codigo=codigo,
                cantidad=Decimal(cantidad),
                costo_unitario=Decimal(costo),
            )
        ],
        **kw,
    )


def _stock(sesion, codigo) -> Decimal:
    return sesion.execute(
        text(
            "select s.cantidad from stock s join articulos a on a.id = s.articulo_id "
            "where a.codigo = :c"
        ),
        {"c": codigo},
    ).scalar()


def _costo(sesion, codigo) -> Decimal:
    return sesion.execute(
        text("select costo from articulos where codigo = :c"), {"c": codigo}
    ).scalar_one()


def _precio(sesion, org, *, codigo_art, codigo_lista) -> Decimal:
    art = catalogo.obtener_articulo(sesion, org.id, codigo_art)
    lista = catalogo.obtener_lista_precio(sesion, org.id, codigo_lista)
    fila = catalogo.precio_de_articulo(sesion, org.id, articulo_id=art.id, lista_id=lista.id)
    return fila.precio


def _proveedor_id(sesion, codigo="PROV-1") -> int:
    return sesion.execute(
        text("select id from proveedores where codigo = :c"), {"c": codigo}
    ).scalar_one()


# =========================================================== IVA + stock + costo + reprice


def test_compra_calcula_iva_suma_stock_actualiza_costo_y_repricea(sesion, org):
    compra = service.crear_compra(sesion, org.id, datos=_compra(cantidad="1", costo="200"))

    assert compra.neto == Decimal("200.00")
    assert compra.iva == Decimal("42.00")  # 21% de 200
    assert compra.total == Decimal("242.00")
    assert _stock(sesion, "BUJIA-1") == Decimal("11.00")  # 10 + 1
    assert _costo(sesion, "BUJIA-1") == Decimal("200.0000")  # último costo pisa
    # MOST tiene margen 50 → 200 * 1.5 = 300. SIN no tiene margen → queda igual.
    assert _precio(sesion, org, codigo_art="BUJIA-1", codigo_lista="MOST") == Decimal("300.00")
    assert _precio(sesion, org, codigo_art="BUJIA-1", codigo_lista="SIN") == Decimal("999.00")


def test_movimiento_apunta_a_la_compra(sesion, org):
    compra = service.crear_compra(sesion, org.id, datos=_compra(cantidad="3"))

    mov = sesion.execute(
        text(
            "select motivo, cantidad from stock_movimientos "
            "where ref_tipo = 'compra' and ref_id = :id"
        ),
        {"id": compra.id},
    ).one()
    assert mov.motivo == "compra"
    assert mov.cantidad == Decimal("3.00")  # positivo: entra


def test_vinculo_articulo_proveedor_se_upsertea_con_el_costo(sesion, org):
    service.crear_compra(sesion, org.id, datos=_compra(costo="250"))

    costo = sesion.execute(
        text(
            "select ap.costo from articulo_proveedores ap "
            "join articulos a on a.id = ap.articulo_id "
            "join proveedores p on p.id = ap.proveedor_id "
            "where a.codigo = 'BUJIA-1' and p.codigo = 'PROV-1'"
        )
    ).scalar_one()
    assert costo == Decimal("250.0000")


# =========================================================== factura duplicada


def test_factura_duplicada_del_proveedor_falla(sesion, org):
    """El unique (org, proveedor, numero) impide cargar dos veces la misma factura."""
    service.crear_compra(sesion, org.id, datos=_compra(numero="DUP-1"))

    sp = sesion.begin_nested()
    with pytest.raises(IntegrityError):
        service.crear_compra(sesion, org.id, datos=_compra(numero="DUP-1"))
    sp.rollback()


# =========================================================== validaciones


def test_proveedor_inexistente_es_invalido(sesion, org):
    datos = _compra()
    datos.proveedor_codigo = "NO-EXISTE"
    with pytest.raises(service.CompraInvalida, match="proveedor"):
        service.crear_compra(sesion, org.id, datos=datos)


def test_articulo_inexistente_es_invalido(sesion, org):
    with pytest.raises(service.CompraInvalida, match="artículo"):
        service.crear_compra(sesion, org.id, datos=_compra(codigo="NO-EXISTE"))


# =========================================================== cuenta corriente de proveedor


def test_compra_a_credito_genera_debe_y_saldo(sesion, org):
    compra = service.crear_compra(sesion, org.id, datos=_compra(condicion="cta_cte"))
    prov_id = _proveedor_id(sesion)

    mov = sesion.execute(
        text(
            "select tipo, debe, haber, ref_tipo, ref_id from prov_cta_cte_movimientos "
            "where proveedor_id = :p"
        ),
        {"p": prov_id},
    ).one()
    assert mov.tipo == "compra"
    assert mov.debe == compra.total
    assert mov.haber == Decimal("0.00")
    assert (mov.ref_tipo, mov.ref_id) == ("compra", compra.id)
    assert service.saldo_proveedor(sesion, org.id, prov_id) == compra.total


def test_compra_contado_no_toca_cta_cte(sesion, org):
    service.crear_compra(sesion, org.id, datos=_compra(condicion="contado"))
    prov_id = _proveedor_id(sesion)

    total = sesion.execute(
        text("select count(*) from prov_cta_cte_movimientos where proveedor_id = :p"),
        {"p": prov_id},
    ).scalar_one()
    assert total == 0
    assert service.saldo_proveedor(sesion, org.id, prov_id) == Decimal("0")


def test_pago_baja_el_saldo(sesion, org):
    compra = service.crear_compra(sesion, org.id, datos=_compra(condicion="cta_cte"))
    prov_id = _proveedor_id(sesion)

    service.registrar_pago(sesion, org.id, proveedor_codigo="PROV-1", monto=Decimal("42.00"))

    assert service.saldo_proveedor(sesion, org.id, prov_id) == compra.total - Decimal("42.00")


def test_prov_cta_cte_es_append_only(sesion, org):
    service.crear_compra(sesion, org.id, datos=_compra(condicion="cta_cte"))
    prov_id = _proveedor_id(sesion)

    sp = sesion.begin_nested()
    with pytest.raises(Exception, match="permission denied|append-only"):
        sesion.execute(
            text("update prov_cta_cte_movimientos set debe = 0 where proveedor_id = :p"),
            {"p": prov_id},
        )
    sp.rollback()

    sp = sesion.begin_nested()
    with pytest.raises(Exception, match="permission denied|append-only"):
        sesion.execute(
            text("delete from prov_cta_cte_movimientos where proveedor_id = :p"), {"p": prov_id}
        )
    sp.rollback()


# =========================================================== append-only de la compra


def test_compra_es_append_only(sesion, org):
    compra = service.crear_compra(sesion, org.id, datos=_compra())

    sp = sesion.begin_nested()
    with pytest.raises(Exception, match="permission denied|append-only"):
        sesion.execute(text("update compras set total = 0 where id = :id"), {"id": compra.id})
    sp.rollback()

    sp = sesion.begin_nested()
    with pytest.raises(Exception, match="permission denied|append-only"):
        sesion.execute(text("delete from compras where id = :id"), {"id": compra.id})
    sp.rollback()


# =========================================================== atomicidad


def test_compra_es_todo_o_nada(sesion, org, monkeypatch):
    """Si el segundo movimiento de stock falla, no queda ni la compra ni el primer movimiento."""
    antes = sesion.execute(text("select count(*) from compras")).scalar_one()

    real = inventario.registrar_movimiento
    llamadas = {"n": 0}

    def _falla_en_el_segundo(*a, **kw):
        llamadas["n"] += 1
        if llamadas["n"] == 2:
            raise RuntimeError("boom a mitad de la compra")
        return real(*a, **kw)

    monkeypatch.setattr(service.inventario, "registrar_movimiento", _falla_en_el_segundo)

    datos = CompraCrear(
        proveedor_codigo="PROV-1",
        deposito_codigo="CEN",
        numero_comprobante="ATOM-1",
        renglones=[
            RenglonCompraCrear(
                articulo_codigo="BUJIA-1", cantidad=Decimal("1"), costo_unitario=Decimal("100")
            ),
            RenglonCompraCrear(
                articulo_codigo="FILTRO-1", cantidad=Decimal("1"), costo_unitario=Decimal("100")
            ),
        ],
    )

    sp = sesion.begin_nested()
    with pytest.raises(RuntimeError, match="boom"):
        service.crear_compra(sesion, org.id, datos=datos)
    sp.rollback()

    assert sesion.execute(text("select count(*) from compras")).scalar_one() == antes


# =========================================================== RLS


@pytest.fixture(scope="module")
def dos_orgs(migrated_db):
    """Dos orgs COMMITEADAS, con una compra emitida en la A."""
    org_a, org_b = uuid4(), uuid4()
    eng = create_engine(OWNER_URL)
    with Session(eng) as s:
        for org_id, suf in ((org_a, "A"), (org_b, "B")):
            s.add(Organizacion(id=org_id, nombre=f"Org {suf}"))
            s.flush()
            dep = inventario.crear_deposito(s, org_id, codigo="CEN", nombre="Central")
            proveedores.crear_proveedor(s, org_id, codigo=f"PROV-{suf}", razon_social=f"Prov {suf}")
            art = Articulo(org_id=org_id, codigo=f"ART-{suf}", detalle=f"Repuesto {suf}")
            s.add(art)
            s.flush()
            inventario.registrar_movimiento(
                s,
                org_id,
                articulo_id=art.id,
                deposito_id=dep.id,
                cantidad=Decimal("10"),
                motivo="inicial",
            )
        service.crear_compra(
            s,
            org_a,
            datos=CompraCrear(
                proveedor_codigo="PROV-A",
                deposito_codigo="CEN",
                numero_comprobante="A-1",
                renglones=[
                    RenglonCompraCrear(
                        articulo_codigo="ART-A",
                        cantidad=Decimal("1"),
                        costo_unitario=Decimal("50"),
                    )
                ],
            ),
        )
        s.commit()
    eng.dispose()
    return SimpleNamespace(a=org_a, b=org_b)


def _contar_compras(org_id) -> int:
    eng = create_engine(APP_URL)
    conn = eng.connect()
    trans = conn.begin()
    with Session(bind=conn) as s:
        set_guc(s, ORG_GUC, str(org_id))
        total = s.execute(text("select count(*) from compras")).scalar_one()
    trans.rollback()
    conn.close()
    eng.dispose()
    return total


def test_compra_no_se_filtra_entre_orgs(dos_orgs):
    assert _contar_compras(dos_orgs.a) == 1
    assert _contar_compras(dos_orgs.b) == 0
