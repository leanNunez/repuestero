"""Notas de crédito (Fase 2, slice 2). Todo contra Postgres real, sin LLM.

Los que no pueden faltar: la NC total y parcial devuelven stock, la numeración propia 'NC' es
correlativa, no se acredita más de lo vendido (incluyendo NCs previas), la NC de una venta a
crédito baja el saldo (y la de contado NO toca la cta cte), el append-only y el RLS entre orgs.
"""

from decimal import Decimal
from types import SimpleNamespace
from uuid import uuid4

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session

from app.catalogo.models import Articulo
from app.clientes import service as clientes
from app.core.db import ORG_GUC, set_guc
from app.core.models import Organizacion
from app.inventario import service as inventario
from app.ventas import service
from app.ventas.schemas import (
    NotaCreditoCrear,
    RenglonNotaCreditoCrear,
    RenglonVentaCrear,
    VentaCrear,
)
from tests.conftest import APP_URL, OWNER_URL

USUARIO = uuid4()


@pytest.fixture(scope="module")
def org(migrated_db):
    """Org con depósito, un cliente y dos artículos con 10 de stock cada uno."""
    org_id = uuid4()
    eng = create_engine(OWNER_URL)
    with Session(eng) as s:
        s.add(Organizacion(id=org_id, nombre="Org NC"))
        s.flush()
        dep = inventario.crear_deposito(s, org_id, codigo="CEN", nombre="Central")
        clientes.crear_cliente(s, org_id, codigo="CLI-1", denominacion="Cliente Uno")
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
            inventario.registrar_movimiento(
                s,
                org_id,
                articulo_id=art.id,
                deposito_id=dep.id,
                cantidad=Decimal("10"),
                motivo="inicial",
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


def _vender(sesion, org, *, cantidad="2", precio="100", codigo="BUJIA-1", condicion="contado"):
    return service.crear_venta(
        sesion,
        org.id,
        datos=VentaCrear(
            cliente_codigo="CLI-1",
            deposito_codigo="CEN",
            condicion=condicion,
            renglones=[
                RenglonVentaCrear(
                    articulo_codigo=codigo,
                    cantidad=Decimal(cantidad),
                    precio_unitario=Decimal(precio),
                )
            ],
        ),
        usuario_id=USUARIO,
    )


def _nc(comprobante_id, renglones=None):
    return NotaCreditoCrear(comprobante_id=comprobante_id, renglones=renglones)


def _stock(sesion, codigo) -> Decimal:
    """Lee la VISTA stock, nunca un número guardado."""
    return sesion.execute(
        text(
            "select s.cantidad from stock s join articulos a on a.id = s.articulo_id "
            "where a.codigo = :c"
        ),
        {"c": codigo},
    ).scalar()


def _cliente_id(sesion, codigo="CLI-1") -> int:
    return sesion.execute(
        text("select id from clientes where codigo = :c"), {"c": codigo}
    ).scalar_one()


# =========================================================== NC total


def test_nc_total_espeja_renglones_y_devuelve_stock(sesion, org):
    comp = _vender(sesion, org, cantidad="2", precio="100")
    assert _stock(sesion, "BUJIA-1") == Decimal("8.00")

    nota = service.crear_nota_credito(sesion, org.id, datos=_nc(comp.id), usuario_id=USUARIO)

    assert nota.tipo == "NC"
    assert nota.numero == 1
    assert nota.ref_comprobante_id == comp.id
    # Espeja el comprobante: mismos importes.
    assert (nota.neto, nota.iva, nota.total) == (comp.neto, comp.iva, comp.total)
    # El stock volvió entero.
    assert _stock(sesion, "BUJIA-1") == Decimal("10.00")

    item = service.items_de_nota_credito(sesion, org.id, nota.id)[0]
    assert item.cantidad == Decimal("2.00")
    assert item.precio_unitario == Decimal("100.00")  # congelado del original


def test_nc_movimiento_es_devolucion_apuntando_a_la_nc(sesion, org):
    comp = _vender(sesion, org, cantidad="3")
    nota = service.crear_nota_credito(sesion, org.id, datos=_nc(comp.id))

    mov = sesion.execute(
        text(
            "select motivo, cantidad from stock_movimientos "
            "where ref_tipo = 'nota_credito' and ref_id = :id"
        ),
        {"id": nota.id},
    ).one()
    assert mov.motivo == "devolucion"
    assert mov.cantidad == Decimal("3.00")  # positivo: vuelve al stock


def test_nc_numeracion_correlativa(sesion, org):
    """Dos NCs (de dos ventas distintas) → 1 y 2, con su propia serie 'NC'."""
    c1 = _vender(sesion, org, cantidad="1")
    c2 = _vender(sesion, org, cantidad="1")
    n1 = service.crear_nota_credito(sesion, org.id, datos=_nc(c1.id))
    n2 = service.crear_nota_credito(sesion, org.id, datos=_nc(c2.id))
    assert (n1.numero, n2.numero) == (1, 2)


# =========================================================== NC parcial


def test_nc_parcial_acredita_subconjunto(sesion, org):
    comp = _vender(sesion, org, cantidad="5", precio="100")
    assert _stock(sesion, "BUJIA-1") == Decimal("5.00")

    nota = service.crear_nota_credito(
        sesion,
        org.id,
        datos=_nc(comp.id, [RenglonNotaCreditoCrear(articulo_codigo="BUJIA-1", cantidad="2")]),
    )

    assert nota.neto == Decimal("200.00")  # 2 * 100
    assert nota.total == Decimal("242.00")
    assert _stock(sesion, "BUJIA-1") == Decimal("7.00")  # 5 + 2 devueltos


def test_nc_no_acredita_mas_de_lo_vendido(sesion, org):
    comp = _vender(sesion, org, cantidad="2")
    with pytest.raises(service.NotaCreditoInvalida, match="restan"):
        service.crear_nota_credito(
            sesion,
            org.id,
            datos=_nc(comp.id, [RenglonNotaCreditoCrear(articulo_codigo="BUJIA-1", cantidad="3")]),
        )


def test_nc_previa_cuenta_para_el_restante(sesion, org):
    """El restante descuenta las NCs anteriores: vendí 5, acredité 3, no puedo acreditar otras 3."""
    comp = _vender(sesion, org, cantidad="5")
    service.crear_nota_credito(
        sesion,
        org.id,
        datos=_nc(comp.id, [RenglonNotaCreditoCrear(articulo_codigo="BUJIA-1", cantidad="3")]),
    )
    with pytest.raises(service.NotaCreditoInvalida, match="restan"):
        service.crear_nota_credito(
            sesion,
            org.id,
            datos=_nc(comp.id, [RenglonNotaCreditoCrear(articulo_codigo="BUJIA-1", cantidad="3")]),
        )


def test_nc_rechaza_articulo_que_no_esta_en_la_venta(sesion, org):
    comp = _vender(sesion, org, cantidad="2", codigo="BUJIA-1")
    with pytest.raises(service.NotaCreditoInvalida, match="no está en la venta"):
        service.crear_nota_credito(
            sesion,
            org.id,
            datos=_nc(comp.id, [RenglonNotaCreditoCrear(articulo_codigo="FILTRO-1", cantidad="1")]),
        )


def test_nc_venta_inexistente_es_invalida(sesion, org):
    with pytest.raises(service.NotaCreditoInvalida, match="No existe la venta"):
        service.crear_nota_credito(sesion, org.id, datos=_nc(999999))


def test_nc_total_sobre_venta_ya_acreditada_falla(sesion, org):
    comp = _vender(sesion, org, cantidad="2")
    service.crear_nota_credito(sesion, org.id, datos=_nc(comp.id))  # total
    with pytest.raises(service.NotaCreditoInvalida, match="totalmente acreditada"):
        service.crear_nota_credito(sesion, org.id, datos=_nc(comp.id))


# =========================================================== acreditables (precarga de la UI)


def test_renglones_acreditables_reflejan_el_restante(sesion, org):
    comp = _vender(sesion, org, cantidad="5", precio="100")
    service.crear_nota_credito(
        sesion,
        org.id,
        datos=_nc(comp.id, [RenglonNotaCreditoCrear(articulo_codigo="BUJIA-1", cantidad="2")]),
    )

    renglones = service.renglones_acreditables(sesion, org.id, comp.id)

    assert len(renglones) == 1
    r = renglones[0]
    assert r.articulo_codigo == "BUJIA-1"
    assert r.cantidad_vendida == Decimal("5.00")
    assert r.cantidad_acreditable == Decimal("3.00")  # 5 - 2 ya acreditados
    assert r.precio_unitario == Decimal("100.00")


# =========================================================== cuenta corriente


def test_nc_a_credito_genera_haber_y_baja_saldo(sesion, org):
    comp = _vender(sesion, org, cantidad="2", condicion="cta_cte")
    cliente_id = _cliente_id(sesion)
    assert service.saldo_cliente(sesion, org.id, cliente_id) == comp.total

    nota = service.crear_nota_credito(sesion, org.id, datos=_nc(comp.id))

    mov = sesion.execute(
        text(
            "select tipo, debe, haber, ref_tipo, ref_id from cta_cte_movimientos "
            "where tipo = 'nota_credito' and ref_id = :id"
        ),
        {"id": nota.id},
    ).one()
    assert mov.tipo == "nota_credito"
    assert mov.haber == nota.total
    assert mov.debe == Decimal("0.00")
    assert (mov.ref_tipo, mov.ref_id) == ("nota_credito", nota.id)
    # Debe (venta) menos Haber (NC) = 0.
    assert service.saldo_cliente(sesion, org.id, cliente_id) == Decimal("0.00")


def test_nc_contado_no_toca_cta_cte(sesion, org):
    comp = _vender(sesion, org, cantidad="2", condicion="contado")
    cliente_id = _cliente_id(sesion)

    service.crear_nota_credito(sesion, org.id, datos=_nc(comp.id))

    total = sesion.execute(
        text("select count(*) from cta_cte_movimientos where cliente_id = :c"),
        {"c": cliente_id},
    ).scalar_one()
    assert total == 0
    assert service.saldo_cliente(sesion, org.id, cliente_id) == Decimal("0")


# =========================================================== append-only


def test_nc_es_append_only(sesion, org):
    """La NC no se edita ni se borra: `app_user` tiene UPDATE/DELETE revocado (choca con
    'permission denied'), el trigger es el backstop. La `sesion` corre como app_user."""
    comp = _vender(sesion, org, cantidad="2")
    nota = service.crear_nota_credito(sesion, org.id, datos=_nc(comp.id))

    sp = sesion.begin_nested()
    with pytest.raises(Exception, match="permission denied|append-only"):
        sesion.execute(text("update notas_credito set total = 0 where id = :id"), {"id": nota.id})
    sp.rollback()

    sp = sesion.begin_nested()
    with pytest.raises(Exception, match="permission denied|append-only"):
        sesion.execute(text("delete from notas_credito where id = :id"), {"id": nota.id})
    sp.rollback()


# =========================================================== atomicidad


def test_nc_es_todo_o_nada(sesion, org, monkeypatch):
    """Si falla el segundo movimiento de devolución, no queda ni la NC ni el primer movimiento."""
    # Venta de dos artículos → la NC total genera dos devoluciones de stock.
    comp = service.crear_venta(
        sesion,
        org.id,
        datos=VentaCrear(
            cliente_codigo="CLI-1",
            deposito_codigo="CEN",
            renglones=[
                RenglonVentaCrear(
                    articulo_codigo="BUJIA-1", cantidad=Decimal("1"), precio_unitario=Decimal("100")
                ),
                RenglonVentaCrear(
                    articulo_codigo="FILTRO-1",
                    cantidad=Decimal("1"),
                    precio_unitario=Decimal("100"),
                ),
            ],
        ),
    )
    antes = sesion.execute(text("select count(*) from notas_credito")).scalar_one()

    real = inventario.registrar_movimiento
    llamadas = {"n": 0}

    def _falla_en_el_segundo(*a, **kw):
        llamadas["n"] += 1
        if llamadas["n"] == 2:
            raise RuntimeError("boom a mitad de la NC")
        return real(*a, **kw)

    monkeypatch.setattr(service.inventario, "registrar_movimiento", _falla_en_el_segundo)

    sp = sesion.begin_nested()
    with pytest.raises(RuntimeError, match="boom"):
        service.crear_nota_credito(sesion, org.id, datos=_nc(comp.id))
    sp.rollback()

    assert sesion.execute(text("select count(*) from notas_credito")).scalar_one() == antes


# =========================================================== RLS


@pytest.fixture(scope="module")
def dos_orgs(migrated_db):
    """Dos orgs COMMITEADAS, con una venta Y su NC emitidas en la A."""
    org_a, org_b = uuid4(), uuid4()
    eng = create_engine(OWNER_URL)
    with Session(eng) as s:
        for org_id, suf in ((org_a, "A"), (org_b, "B")):
            s.add(Organizacion(id=org_id, nombre=f"Org {suf}"))
            s.flush()
            dep = inventario.crear_deposito(s, org_id, codigo="CEN", nombre="Central")
            clientes.crear_cliente(s, org_id, codigo=f"CLI-{suf}", denominacion=f"Cliente {suf}")
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
        comp = service.crear_venta(
            s,
            org_a,
            datos=VentaCrear(
                cliente_codigo="CLI-A",
                deposito_codigo="CEN",
                renglones=[
                    RenglonVentaCrear(
                        articulo_codigo="ART-A",
                        cantidad=Decimal("1"),
                        precio_unitario=Decimal("50"),
                    )
                ],
            ),
        )
        service.crear_nota_credito(s, org_a, datos=NotaCreditoCrear(comprobante_id=comp.id))
        s.commit()
    eng.dispose()
    return SimpleNamespace(a=org_a, b=org_b)


def _contar_notas(org_id) -> int:
    """Cuenta notas de crédito como `app_user` (sujeto a RLS) con el tenant fijado en `org_id`."""
    eng = create_engine(APP_URL)
    conn = eng.connect()
    trans = conn.begin()
    with Session(bind=conn) as s:
        set_guc(s, ORG_GUC, str(org_id))
        total = s.execute(text("select count(*) from notas_credito")).scalar_one()
    trans.rollback()
    conn.close()
    eng.dispose()
    return total


def test_nc_no_se_filtra_entre_orgs(dos_orgs):
    """La org A ve su NC; la org B no la ve ni la cuenta."""
    assert _contar_notas(dos_orgs.a) == 1
    assert _contar_notas(dos_orgs.b) == 0
