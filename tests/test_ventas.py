"""Ventas (Fase 2, slice 1). Todo contra Postgres real, sin LLM.

Los tests que no pueden faltar: el IVA por renglón, la numeración correlativa, el bloqueo por
stock insuficiente, la trazabilidad del movimiento al comprobante, la atomicidad todo-o-nada y
el aislamiento por RLS entre orgs.
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
from app.ventas.schemas import RenglonVentaCrear, VentaCrear
from tests.conftest import APP_URL, OWNER_URL

USUARIO = uuid4()


@pytest.fixture(scope="module")
def org(migrated_db):
    """Org con depósito, un cliente y un artículo con 10 de stock."""
    org_id = uuid4()
    eng = create_engine(OWNER_URL)
    with Session(eng) as s:
        s.add(Organizacion(id=org_id, nombre="Org Ventas"))
        s.flush()
        dep = inventario.crear_deposito(s, org_id, codigo="CEN", nombre="Central")
        clientes.crear_cliente(s, org_id, codigo="CLI-1", denominacion="Cliente Uno")
        art = Articulo(
            org_id=org_id,
            codigo="BUJIA-1",
            detalle="BUJIA NGK BKR6E",
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


def _venta(*, cantidad="2", precio="100", codigo="BUJIA-1", **kw) -> VentaCrear:
    return VentaCrear(
        cliente_codigo="CLI-1",
        deposito_codigo="CEN",
        renglones=[
            RenglonVentaCrear(
                articulo_codigo=codigo,
                cantidad=Decimal(cantidad),
                precio_unitario=Decimal(precio),
            )
        ],
        **kw,
    )


def _stock(sesion, codigo) -> Decimal:
    """Lee la VISTA stock, nunca un número guardado."""
    return sesion.execute(
        text(
            "select s.cantidad from stock s join articulos a on a.id = s.articulo_id "
            "where a.codigo = :c"
        ),
        {"c": codigo},
    ).scalar()


# =========================================================== emisión + IVA + stock


def test_venta_calcula_iva_y_descuenta_stock(sesion, org):
    comp = service.crear_venta(sesion, org.id, datos=_venta(), usuario_id=USUARIO)

    assert comp.numero == 1
    assert comp.neto == Decimal("200.00")
    assert comp.iva == Decimal("42.00")  # 21% de 200
    assert comp.total == Decimal("242.00")
    assert _stock(sesion, "BUJIA-1") == Decimal("8.00")  # 10 - 2


def test_movimiento_apunta_al_comprobante(sesion, org):
    comp = service.crear_venta(sesion, org.id, datos=_venta(), usuario_id=USUARIO)

    mov = sesion.execute(
        text(
            "select motivo, ref_tipo, ref_id, cantidad from stock_movimientos "
            "where ref_tipo = 'comprobante_venta' and ref_id = :id"
        ),
        {"id": comp.id},
    ).one()
    assert mov.motivo == "venta"
    assert mov.cantidad == Decimal("-2.00")  # negativo: sale


# =========================================================== numeración


def test_numeracion_correlativa(sesion, org):
    """Dos ventas seguidas del mismo (tipo, pto_venta) → 1 y 2, sin saltos ni repetidos."""
    c1 = service.crear_venta(sesion, org.id, datos=_venta())
    c2 = service.crear_venta(sesion, org.id, datos=_venta())
    assert (c1.numero, c2.numero) == (1, 2)


# =========================================================== stock insuficiente


def test_stock_insuficiente_bloquea(sesion, org):
    """No se vende lo que no hay: la venta se rechaza y el stock queda intacto."""
    with pytest.raises(service.VentaInvalida, match="Stock insuficiente"):
        service.crear_venta(sesion, org.id, datos=_venta(cantidad="99"))

    assert _stock(sesion, "BUJIA-1") == Decimal("10.00")  # nada se movió


# =========================================================== atomicidad


def test_venta_es_todo_o_nada(sesion, org, monkeypatch):
    """Si el segundo movimiento de stock falla, NO queda ni el comprobante ni el primer
    movimiento. No existe la venta a medias."""
    antes = sesion.execute(text("select count(*) from comprobantes")).scalar_one()

    real = inventario.registrar_movimiento
    llamadas = {"n": 0}

    def _falla_en_el_segundo(*a, **kw):
        llamadas["n"] += 1
        if llamadas["n"] == 2:
            raise RuntimeError("boom a mitad de la venta")
        return real(*a, **kw)

    monkeypatch.setattr(service.inventario, "registrar_movimiento", _falla_en_el_segundo)

    datos = VentaCrear(
        cliente_codigo="CLI-1",
        deposito_codigo="CEN",
        renglones=[
            RenglonVentaCrear(
                articulo_codigo="BUJIA-1", cantidad=Decimal("1"), precio_unitario=Decimal("100")
            ),
            RenglonVentaCrear(
                articulo_codigo="BUJIA-1", cantidad=Decimal("1"), precio_unitario=Decimal("100")
            ),
        ],
    )

    sp = sesion.begin_nested()
    with pytest.raises(RuntimeError, match="boom"):
        service.crear_venta(sesion, org.id, datos=datos)
    sp.rollback()

    assert sesion.execute(text("select count(*) from comprobantes")).scalar_one() == antes
    assert _stock(sesion, "BUJIA-1") == Decimal("10.00")  # nada salió


# =========================================================== RLS


@pytest.fixture(scope="module")
def dos_orgs(migrated_db):
    """Dos orgs COMMITEADAS (bypass RLS como owner), con una venta emitida en la A.

    La venta se commitea de verdad para poder verificar la visibilidad cruzada: una fila sin
    commitear no la vería otra conexión ni aunque RLS fallara.
    """
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
        # La org A emite UNA venta.
        service.crear_venta(
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
        s.commit()
    eng.dispose()
    return SimpleNamespace(a=org_a, b=org_b)


def _contar_comprobantes(org_id) -> int:
    """Cuenta comprobantes como `app_user` (sujeto a RLS) con el tenant fijado en `org_id`."""
    eng = create_engine(APP_URL)
    conn = eng.connect()
    trans = conn.begin()
    with Session(bind=conn) as s:
        set_guc(s, ORG_GUC, str(org_id))
        total = s.execute(text("select count(*) from comprobantes")).scalar_one()
    trans.rollback()
    conn.close()
    eng.dispose()
    return total


def test_venta_no_se_filtra_entre_orgs(dos_orgs):
    """La org A ve su comprobante; la org B no lo ve ni lo cuenta."""
    assert _contar_comprobantes(dos_orgs.a) == 1
    assert _contar_comprobantes(dos_orgs.b) == 0


# =========================================================== cuenta corriente


def _cliente_id(sesion, codigo="CLI-1") -> int:
    return sesion.execute(
        text("select id from clientes where codigo = :c"), {"c": codigo}
    ).scalar_one()


def test_venta_a_credito_genera_debe_y_saldo(sesion, org):
    """Una venta a cuenta corriente carga un Debe; el saldo del cliente = total del comprobante."""
    comp = service.crear_venta(sesion, org.id, datos=_venta(condicion="cta_cte"))
    cliente_id = _cliente_id(sesion)

    mov = sesion.execute(
        text(
            "select tipo, debe, haber, ref_tipo, ref_id from cta_cte_movimientos "
            "where cliente_id = :c"
        ),
        {"c": cliente_id},
    ).one()
    assert mov.tipo == "venta"
    assert mov.debe == comp.total
    assert mov.haber == Decimal("0.00")
    assert (mov.ref_tipo, mov.ref_id) == ("comprobante", comp.id)

    assert service.saldo_cliente(sesion, org.id, cliente_id) == comp.total


def test_venta_contado_no_toca_cta_cte(sesion, org):
    """La venta al contado no genera movimiento de cuenta corriente."""
    service.crear_venta(sesion, org.id, datos=_venta(condicion="contado"))
    cliente_id = _cliente_id(sesion)

    total = sesion.execute(
        text("select count(*) from cta_cte_movimientos where cliente_id = :c"),
        {"c": cliente_id},
    ).scalar_one()
    assert total == 0
    assert service.saldo_cliente(sesion, org.id, cliente_id) == Decimal("0")


def test_cobranza_baja_el_saldo(sesion, org):
    """Una cobranza es un Haber: baja el saldo que dejó la venta a crédito."""
    comp = service.crear_venta(sesion, org.id, datos=_venta(condicion="cta_cte"))
    cliente_id = _cliente_id(sesion)

    service.registrar_cobranza(sesion, org.id, cliente_codigo="CLI-1", monto=Decimal("42.00"))

    assert service.saldo_cliente(sesion, org.id, cliente_id) == comp.total - Decimal("42.00")


def test_cta_cte_es_append_only(sesion, org):
    """El ledger no se edita ni se borra. Dos barreras: `app_user` tiene UPDATE/DELETE revocado
    (choca con 'permission denied'), y el trigger es el backstop para quien igual tenga el grant
    (el owner). La `sesion` corre como app_user, así que verificamos la primera barrera."""
    service.crear_venta(sesion, org.id, datos=_venta(condicion="cta_cte"))
    cliente_id = _cliente_id(sesion)

    sp = sesion.begin_nested()
    with pytest.raises(Exception, match="permission denied|append-only"):
        sesion.execute(
            text("update cta_cte_movimientos set debe = 0 where cliente_id = :c"),
            {"c": cliente_id},
        )
    sp.rollback()

    sp = sesion.begin_nested()
    with pytest.raises(Exception, match="permission denied|append-only"):
        sesion.execute(
            text("delete from cta_cte_movimientos where cliente_id = :c"), {"c": cliente_id}
        )
    sp.rollback()
