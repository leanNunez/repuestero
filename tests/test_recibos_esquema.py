"""Las guardas que la base impone sobre recibos y órdenes de pago (migración 0010).

Esto NO testea comportamiento: todavía no hay service que emita recibos. Testea que el ESQUEMA
haga cumplir lo que el diseño promete, porque estas cuatro tablas son append-only y un invariante
que no se hace cumplir acá es un dato roto sin arreglo posible.

Lo que no puede faltar:
- Append-only de verdad (REVOKE + trigger), en el documento Y en su detalle.
- Que las formas de pago sumen EXACTO el total, incluido el caso "cero renglones", que es el que
  más fácil se escapa: si el trigger estuviera solo sobre la tabla hija, un documento sin detalle
  no dispararía nada.
- Que el catálogo de formas de Python y el CHECK congelado en la migración no se separen.
- Que la FK compuesta impida colgar un renglón del documento de otra organización.

Todo contra Postgres real, patrón A (app_user, sujeto a RLS). El trigger de la suma es DIFERIDO:
se evalúa en el COMMIT, y estos tests hacen rollback. Sin `set constraints all immediate` pasarían
todos en verde sin haber probado nada — de ahí el helper `_cerrar`.
"""

from collections.abc import Iterator
from contextlib import contextmanager
from datetime import date
from decimal import Decimal
from types import SimpleNamespace
from uuid import uuid4

import pytest
from sqlalchemy import create_engine, select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.clientes import service as clientes
from app.compras.models import OrdenPago, OrdenPagoFormaPago
from app.core.db import ORG_GUC, set_guc
from app.core.formas_pago import FORMAS_PAGO
from app.core.models import Organizacion
from app.proveedores import service as proveedores
from app.ventas.models import Recibo, ReciboFormaPago
from tests.conftest import APP_URL, OWNER_URL


@pytest.fixture(scope="module")
def org(migrated_db):
    """Una org con un cliente y un proveedor, más una vecina con un recibo que no debe verse."""
    org_id, vecina_id = uuid4(), uuid4()
    eng = create_engine(OWNER_URL)
    with Session(eng) as s:
        s.add(Organizacion(id=org_id, nombre="Org Recibos"))
        s.add(Organizacion(id=vecina_id, nombre="Org Vecina"))
        s.flush()

        cli = clientes.crear_cliente(s, org_id, codigo="CLI-REC", denominacion="Ferretería Alsina")
        prov = proveedores.crear_proveedor(
            s, org_id, codigo="PROV-OP", razon_social="Bosch Argentina"
        )

        ajeno = clientes.crear_cliente(s, vecina_id, codigo="CLI-X", denominacion="No Se Ve SA")
        vecino = Recibo(
            org_id=vecina_id,
            cliente_id=ajeno.id,
            tipo="REC",
            pto_venta=1,
            numero=1,
            fecha=date(2026, 5, 1),
            total=Decimal("99999"),
        )
        s.add(vecino)
        s.flush()
        s.add(
            ReciboFormaPago(
                org_id=vecina_id, recibo_id=vecino.id, forma="efectivo", monto=Decimal("99999")
            )
        )
        s.commit()
        ids = SimpleNamespace(cliente=cli.id, proveedor=prov.id, recibo_vecino=vecino.id)
    eng.dispose()
    return SimpleNamespace(id=org_id, vecina=vecina_id, **ids.__dict__)


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


def _cerrar(sesion) -> None:
    """Fuerza la evaluación de los constraint triggers diferidos SIN commitear.

    Es lo que haría el COMMIT de `get_tenant`. Sin esto, un test que hace rollback nunca los
    dispara y verifica exactamente nada.

    Vuelve a `deferred` enseguida, y no es cosmético: `set constraints all immediate` queda activo
    para TODA la transacción, así que sin restaurarlo el próximo INSERT de un renglón se evaluaría
    solo —viendo el documento a medio armar— en vez de esperar al cierre. Cada `_cerrar` simula un
    commit puntual y deja la sesión como estaba.
    """
    sesion.flush()
    sesion.execute(text("set constraints all immediate"))
    sesion.execute(text("set constraints all deferred"))


@contextmanager
def _rechaza(sesion, patron: str) -> Iterator[None]:
    """Espera que la BASE rechace lo de adentro, sin dejar la transacción abortada.

    El savepoint es lo que deja seguir usando la sesión después del error (y que el rollback de
    la fixture no proteste). Mismo patrón que `tests/test_compras.py`.
    """
    sp = sesion.begin_nested()
    with pytest.raises(IntegrityError, match=patron):
        yield
    sp.rollback()


def _recibo(sesion, org, *, numero: int = 1, total: str = "1000", pto_venta: int = 1) -> Recibo:
    """Inserta la cabecera. Todavía NO cierra: el detalle lo pone cada test."""
    r = Recibo(
        org_id=org.id,
        cliente_id=org.cliente,
        tipo="REC",
        pto_venta=pto_venta,
        numero=numero,
        total=Decimal(total),
    )
    sesion.add(r)
    sesion.flush()
    return r


def _forma(sesion, org, recibo: Recibo, *, forma: str = "efectivo", monto: str = "1000") -> None:
    sesion.add(
        ReciboFormaPago(org_id=org.id, recibo_id=recibo.id, forma=forma, monto=Decimal(monto))
    )


# =========================================================================== append-only


def test_el_recibo_no_se_puede_editar(sesion, org):
    """Un recibo es papel entregado al cliente. Se corrige revirtiendo el movimiento, no editando."""
    r = _recibo(sesion, org)
    _forma(sesion, org, r)
    _cerrar(sesion)

    sp = sesion.begin_nested()
    with pytest.raises(Exception, match="permission denied|no se edita"):
        sesion.execute(text("update recibos set total = 1 where id = :i"), {"i": r.id})
    sp.rollback()

    sp = sesion.begin_nested()
    with pytest.raises(Exception, match="permission denied|no se edita"):
        sesion.execute(text("delete from recibos where id = :i"), {"i": r.id})
    sp.rollback()


def test_las_formas_de_pago_no_se_pueden_editar_ni_borrar(sesion, org):
    """Si el detalle fuera mutable, el invariante de la suma se podría romper DESPUÉS de validado."""
    r = _recibo(sesion, org)
    _forma(sesion, org, r)
    _cerrar(sesion)

    sp = sesion.begin_nested()
    with pytest.raises(Exception, match="permission denied|no se edita"):
        sesion.execute(
            text("update recibo_formas_pago set monto = 1 where recibo_id = :i"), {"i": r.id}
        )
    sp.rollback()

    sp = sesion.begin_nested()
    with pytest.raises(Exception, match="permission denied|no se edita"):
        sesion.execute(text("delete from recibo_formas_pago where recibo_id = :i"), {"i": r.id})
    sp.rollback()


def test_la_orden_de_pago_tambien_es_append_only(sesion, org):
    op = OrdenPago(
        org_id=org.id,
        proveedor_id=org.proveedor,
        tipo="OP",
        pto_venta=1,
        numero=1,
        total=Decimal("500"),
    )
    sesion.add(op)
    sesion.flush()
    sesion.add(
        OrdenPagoFormaPago(
            org_id=org.id, orden_pago_id=op.id, forma="transferencia", monto=Decimal("500")
        )
    )
    _cerrar(sesion)

    sp = sesion.begin_nested()
    with pytest.raises(Exception, match="permission denied|no se edita"):
        sesion.execute(text("update ordenes_pago set total = 1 where id = :i"), {"i": op.id})
    sp.rollback()


# =========================================================================== la suma tiene que cerrar


def test_un_recibo_con_su_forma_de_pago_cierra(sesion, org):
    """El caso feliz: si esto fallara, el trigger estaría rechazando todo."""
    r = _recibo(sesion, org, total="1000")
    _forma(sesion, org, r, monto="1000")
    _cerrar(sesion)

    assert sesion.scalar(select(Recibo.total).where(Recibo.id == r.id)) == Decimal("1000")


def test_un_pago_mixto_cierra(sesion, org):
    """Efectivo + cheque sumando el total. Es el caso que justifica que el detalle sea 1:N."""
    r = _recibo(sesion, org, total="20000")
    _forma(sesion, org, r, forma="efectivo", monto="5000")
    _forma(sesion, org, r, forma="cheque", monto="15000")
    _cerrar(sesion)

    total = sesion.scalar(
        select(ReciboFormaPago.monto).where(ReciboFormaPago.recibo_id == r.id).limit(1)
    )
    assert total is not None


def test_dos_cheques_en_el_mismo_recibo_son_legitimos(sesion, org):
    """Sin unique (recibo, forma) a propósito: cuando llegue la cartera, cada renglón es un cheque."""
    r = _recibo(sesion, org, total="30000")
    _forma(sesion, org, r, forma="cheque", monto="10000")
    _forma(sesion, org, r, forma="cheque", monto="20000")
    _cerrar(sesion)


def test_insertar_una_forma_de_mas_rompe_el_commit(sesion, org):
    """El agujero que el trigger existe para tapar.

    `_blindar_append_only` revoca UPDATE y DELETE, pero NO INSERT: sin este trigger, cualquiera
    puede colgarle un renglón de más a un recibo ya cerrado, y en una tabla append-only eso no
    tiene arreglo.
    """
    r = _recibo(sesion, org, total="1000")
    _forma(sesion, org, r, monto="1000")
    _cerrar(sesion)

    _forma(sesion, org, r, forma="tarjeta", monto="1")
    with _rechaza(sesion, "suman"):
        _cerrar(sesion)


def test_un_recibo_sin_formas_de_pago_no_puede_cerrar(sesion, org):
    """El caso que se escapa si el trigger está solo sobre la tabla hija: sin hijos no dispara."""
    _recibo(sesion, org, total="1000")

    with _rechaza(sesion, "suman"):
        _cerrar(sesion)


def test_formas_que_no_llegan_al_total_no_cierran(sesion, org):
    r = _recibo(sesion, org, total="1000")
    _forma(sesion, org, r, monto="999.99")

    with _rechaza(sesion, "suman"):
        _cerrar(sesion)


def test_la_orden_de_pago_tambien_exige_que_cierre(sesion, org):
    op = OrdenPago(
        org_id=org.id,
        proveedor_id=org.proveedor,
        tipo="OP",
        pto_venta=1,
        numero=2,
        total=Decimal("800"),
    )
    sesion.add(op)

    with _rechaza(sesion, "suman"):
        _cerrar(sesion)


# =========================================================================== catálogo de formas


def test_el_catalogo_de_python_y_el_check_de_la_base_coinciden(sesion, org):
    """El candado de la constante compartida.

    `FORMAS_PAGO` vive en `app/core/formas_pago.py`, pero la migración congela su propia copia en
    el CHECK (una migración no puede importar código que cambia). Si alguien agrega una forma en
    Python sin migrar, este test lo caza acá y no en producción.
    """
    formas = sorted(FORMAS_PAGO)
    r = _recibo(sesion, org, total=str(100 * len(formas)))
    for f in formas:
        _forma(sesion, org, r, forma=f, monto="100")
    _cerrar(sesion)

    guardadas = sesion.scalars(
        select(ReciboFormaPago.forma).where(ReciboFormaPago.recibo_id == r.id)
    ).all()
    assert sorted(guardadas) == formas


def test_el_check_rechaza_una_forma_inventada(sesion, org):
    r = _recibo(sesion, org, total="1000")

    with _rechaza(sesion, "ck_recibo_formas_pago_forma"):
        _forma(sesion, org, r, forma="bitcoin", monto="1000")
        sesion.flush()


def test_un_renglon_no_puede_ser_cero_ni_negativo(sesion, org):
    r = _recibo(sesion, org, total="1000")

    with _rechaza(sesion, "ck_recibo_formas_pago_monto_positivo"):
        _forma(sesion, org, r, monto="0")
        sesion.flush()


def test_un_recibo_no_puede_tener_total_cero(sesion, org):
    """Un recibo por $0 no es un cobro: es ruido en el ledger y en la numeración."""
    with _rechaza(sesion, "ck_recibos_total_positivo"):
        _recibo(sesion, org, total="0")


# =========================================================================== aislamiento por org


def test_el_recibo_de_otra_org_no_se_ve(sesion, org):
    """RLS. La org vecina tiene un recibo sembrado; desde acá no existe."""
    assert sesion.get(Recibo, org.recibo_vecino) is None
    assert sesion.scalars(select(Recibo)).all() == []


def test_una_forma_no_puede_apuntar_al_recibo_de_otra_org(sesion, org):
    """Lo que justifica que la FK sea COMPUESTA (org_id, recibo_id).

    Con una FK simple esto entraría: el trigger de la suma corre bajo RLS, no vería el recibo
    vecino, devolvería `not found` y dejaría pasar el renglón EN SILENCIO. La FK no mira RLS, así
    que ve que el par (mi org, recibo ajeno) no existe y lo rechaza.
    """
    with _rechaza(sesion, "fk_recibo_formas_pago_recibos"):
        sesion.add(
            ReciboFormaPago(
                org_id=org.id,
                recibo_id=org.recibo_vecino,
                forma="efectivo",
                monto=Decimal("99999"),
            )
        )
        sesion.flush()


# =========================================================================== numeración


def test_numeracion_duplicada_choca_contra_el_unique(sesion, org):
    """El árbitro final de la numeración, igual que en comprobantes: el lock da el correlativo,
    el unique es el que no perdona."""
    r = _recibo(sesion, org, numero=7, total="100")
    _forma(sesion, org, r, monto="100")
    _cerrar(sesion)

    with _rechaza(sesion, "uq_recibos_org_tipo_pv_num"):
        _recibo(sesion, org, numero=7, total="200")


def test_el_mismo_numero_en_otro_punto_de_venta_convive(sesion, org):
    """La numeración es por (tipo, punto de venta): dos mostradores no comparten contador."""
    r1 = _recibo(sesion, org, numero=1, pto_venta=1, total="100")
    _forma(sesion, org, r1, monto="100")
    r2 = _recibo(sesion, org, numero=1, pto_venta=2, total="200")
    _forma(sesion, org, r2, monto="200")
    _cerrar(sesion)

    assert r1.id != r2.id


def test_un_recibo_y_una_orden_de_pago_no_comparten_espacio_de_numeracion(sesion, org):
    """Son tablas distintas: REC #1 y OP #1 conviven sin pisarse."""
    r = _recibo(sesion, org, numero=1, total="100")
    _forma(sesion, org, r, monto="100")

    op = OrdenPago(
        org_id=org.id,
        proveedor_id=org.proveedor,
        tipo="OP",
        pto_venta=1,
        numero=1,
        total=Decimal("300"),
    )
    sesion.add(op)
    sesion.flush()
    sesion.add(
        OrdenPagoFormaPago(
            org_id=org.id, orden_pago_id=op.id, forma="efectivo", monto=Decimal("300")
        )
    )
    _cerrar(sesion)
