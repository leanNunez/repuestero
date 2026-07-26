"""La orden de pago: el espejo del recibo, del lado proveedor.

El recibo lo emite quien COBRA. Cuando le pagamos a un proveedor, el recibo lo emite él y nosotros
emitimos una ORDEN DE PAGO — por eso es otra entidad y no un `Recibo` con un flag.

Lo que no puede faltar, además del espejo de `test_recibos.py`:
- Que los numeradores de 'REC' y 'OP' sean INDEPENDIENTES: si compartieran contador, el primer
  recibo de una org que ya pagó saldría con un número salteado.
- Que `asignar_numero` siga funcionando después de mudarse a `app/core/numeracion.py`.
"""

from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from types import SimpleNamespace
from uuid import uuid4

import jwt
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from app.caja import service as caja
from app.compras import service as compras
from app.compras.models import OrdenPago, OrdenPagoFormaPago, ProvCtaCteMovimiento
from app.core import db as core_db
from app.core.config import get_settings
from app.core.db import ORG_GUC, set_guc
from app.core.models import Miembro, Organizacion
from app.core.numeracion import asignar_numero
from app.main import app
from app.proveedores import service as proveedores
from app.ventas import service as ventas
from tests.conftest import APP_URL, OWNER_URL

EFECTIVO = "efectivo"


@pytest.fixture(scope="module")
def org(migrated_db):
    """Una org a la que ya le debemos plata, más una vecina con su propia orden."""
    org_id, user_id, vecina_id = uuid4(), uuid4(), uuid4()
    eng = create_engine(OWNER_URL)
    with Session(eng) as s:
        s.add(Organizacion(id=org_id, nombre="Org Ordenes"))
        s.add(Organizacion(id=vecina_id, nombre="Org Vecina"))
        s.flush()

        prov = proveedores.crear_proveedor(
            s, org_id, codigo="PROV-OP", razon_social="Bosch Argentina"
        )
        s.add(
            ProvCtaCteMovimiento(
                org_id=org_id,
                proveedor_id=prov.id,
                fecha=date(2026, 1, 12),
                tipo="compra",
                debe=Decimal("100000"),
            )
        )

        ajeno = proveedores.crear_proveedor(
            s, vecina_id, codigo="PROV-X", razon_social="No Se Ve SA"
        )
        vecina_orden = OrdenPago(
            org_id=vecina_id,
            proveedor_id=ajeno.id,
            tipo="OP",
            pto_venta=1,
            numero=1,
            fecha=date(2026, 5, 1),
            total=Decimal("500"),
        )
        s.add(vecina_orden)
        s.flush()
        s.add(
            OrdenPagoFormaPago(
                org_id=vecina_id,
                orden_pago_id=vecina_orden.id,
                forma=EFECTIVO,
                monto=Decimal("500"),
            )
        )

        s.add(Miembro(org_id=org_id, user_id=user_id, rol="admin"))  # sin esto get_tenant da 403
        s.commit()
        ids = SimpleNamespace(proveedor=prov.id, orden_vecina=vecina_orden.id)
    eng.dispose()
    return SimpleNamespace(id=org_id, user=user_id, vecina=vecina_id, **ids.__dict__)


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


def _pagar(sesion, org, monto: str = "1000", **kw):
    m = Decimal(monto)
    formas = kw.pop("formas_pago", [compras.FormaPago(EFECTIVO, m)])
    return compras.registrar_pago(
        sesion, org.id, proveedor_codigo="PROV-OP", monto=m, formas_pago=formas, **kw
    )


# =========================================================================== la orden de pago


def test_el_pago_emite_orden_y_la_referencia(sesion, org):
    """Espejo del test que cierra el issue del lado clientes."""
    pago = _pagar(sesion, org, "1000")

    assert pago.orden.id is not None
    assert pago.movimiento.ref_tipo == "orden_pago"
    assert pago.movimiento.ref_id == pago.orden.id
    assert pago.orden.total == Decimal("1000")
    assert pago.movimiento.haber == Decimal("1000")


def test_la_orden_numera_correlativo_por_punto_de_venta(sesion, org):
    assert _pagar(sesion, org, "10").orden.numero == 1
    assert _pagar(sesion, org, "20").orden.numero == 2
    assert _pagar(sesion, org, "30", pto_venta=2).orden.numero == 1
    assert _pagar(sesion, org, "40").orden.numero == 3


def test_op_y_rec_tienen_numeradores_independientes(sesion, org):
    """REC #1 y OP #1 conviven en la misma organización.

    Si compartieran contador, el primer recibo de una org que ya emitió órdenes de pago saldría
    con un número salteado y sin explicación para el cliente que lo recibe en la mano.
    """
    for _ in range(3):
        asignar_numero(sesion, org.id, tipo=ventas.TIPO_RECIBO, pto_venta=1)

    assert _pagar(sesion, org, "10").orden.numero == 1


def test_asignar_numero_sigue_funcionando_desde_core(sesion, org):
    """Se mudó de `app/ventas/service.py` a `app/core/numeracion.py` (es un move, no una copia:
    dos clases con el mismo __tablename__ explotan al importar)."""
    assert asignar_numero(sesion, org.id, tipo="TEST", pto_venta=9) == 1
    assert asignar_numero(sesion, org.id, tipo="TEST", pto_venta=9) == 2
    assert asignar_numero(sesion, org.id, tipo="TEST", pto_venta=8) == 1


def test_un_pago_mixto_deja_dos_renglones(sesion, org):
    pago = _pagar(
        sesion,
        org,
        "20000",
        formas_pago=[
            compras.FormaPago("transferencia", Decimal("12000")),
            compras.FormaPago("cheque", Decimal("8000")),
        ],
    )

    formas = compras.formas_de_orden_pago(sesion, org.id, pago.orden.id)
    assert [(f.forma, f.monto) for f in formas] == [
        ("transferencia", Decimal("12000")),
        ("cheque", Decimal("8000")),
    ]


def test_la_orden_hereda_la_fecha_del_pago(sesion, org):
    pago = _pagar(sesion, org, "500", fecha=date(2026, 2, 20))

    assert pago.orden.fecha == date(2026, 2, 20)
    assert pago.movimiento.fecha == date(2026, 2, 20)


def test_la_orden_y_el_movimiento_comparten_creado_por(sesion, org):
    usuario = uuid4()
    pago = _pagar(sesion, org, "500", usuario_id=usuario)

    assert pago.orden.creado_por == usuario
    assert pago.movimiento.creado_por == usuario


# =========================================================================== lo que NO entra


def test_formas_que_no_suman_el_total_no_entran(sesion, org):
    with pytest.raises(compras.CompraInvalida, match="suman"):
        _pagar(sesion, org, "1000", formas_pago=[compras.FormaPago(EFECTIVO, Decimal("999.99"))])


def test_formas_vacias_no_entran(sesion, org):
    with pytest.raises(compras.CompraInvalida, match="con qué se pagó"):
        _pagar(sesion, org, "1000", formas_pago=[])


def test_una_forma_inventada_no_entra(sesion, org):
    with pytest.raises(compras.CompraInvalida, match="desconocida"):
        _pagar(sesion, org, "1000", formas_pago=[compras.FormaPago("bitcoin", Decimal("1000"))])


def test_un_pago_en_cero_no_entra(sesion, org):
    with pytest.raises(compras.CompraInvalida, match="mayor a cero"):
        _pagar(sesion, org, "0")


def test_un_proveedor_inexistente_no_emite_orden(sesion, org):
    """Y no consume número: el proveedor se resuelve antes de numerar."""
    with pytest.raises(compras.CompraInvalida, match="No existe el proveedor"):
        compras.registrar_pago(
            sesion,
            org.id,
            proveedor_codigo="NO-EXISTE",
            monto=Decimal("100"),
            formas_pago=[compras.FormaPago(EFECTIVO, Decimal("100"))],
        )

    assert _pagar(sesion, org, "100").orden.numero == 1


# =========================================================================== orden vs. ajuste


def test_anular_un_pago_no_borra_su_orden(sesion, org):
    pago = _pagar(sesion, org, "1000")
    compras.anular_orden_pago(sesion, org.id, pago.orden.id, motivo="pagué de más")

    assert compras.obtener_orden_pago(sesion, org.id, pago.orden.id) is not None


def test_la_reversa_apunta_al_movimiento_y_no_a_la_orden(sesion, org):
    pago = _pagar(sesion, org, "1000")
    reversa = compras.anular_orden_pago(sesion, org.id, pago.orden.id, motivo="pagué de más")

    assert (reversa.ref_tipo, reversa.ref_id) == ("ajuste_de", pago.movimiento.id)


def test_el_extracto_muestra_la_referencia_del_pago(sesion, org):
    """La solapa de proveedores dejaba la columna Referencia vacía en los pagos."""
    pago = _pagar(sesion, org, "1000")

    filas, _ = compras.movimientos_proveedor(sesion, org.id, org.proveedor, limite=100)
    fila = next(f for f in filas if f.id == pago.movimiento.id)
    assert (fila.ref_tipo, fila.ref_id) == ("orden_pago", pago.orden.id)


def test_un_pago_viejo_sin_orden_sigue_leyendose(sesion, org):
    """La decisión de no backfillear, del lado proveedor."""
    viejo = ProvCtaCteMovimiento(
        org_id=org.id,
        proveedor_id=org.proveedor,
        fecha=date(2026, 3, 1),
        tipo="pago",
        haber=Decimal("777"),
    )
    sesion.add(viejo)
    sesion.flush()

    filas, _ = compras.movimientos_proveedor(sesion, org.id, org.proveedor, limite=100)
    fila = next(f for f in filas if f.id == viejo.id)
    assert fila.ref_tipo is None
    # Espejo de la nota en `test_recibos`: 'pago' salió de MOVIMIENTOS_REVERSIBLES para todos,
    # viejos incluidos. Estos no tienen orden que anular y se corrigen con un ajuste MANUAL.
    assert fila.reversible is False


# =========================================================================== lecturas


def test_obtener_orden_de_otra_org_es_none(sesion, org):
    assert compras.obtener_orden_pago(sesion, org.id, org.orden_vecina) is None


def test_formas_de_una_orden_ajena_no_se_ven(sesion, org):
    assert compras.formas_de_orden_pago(sesion, org.id, org.orden_vecina) == []


def test_la_orden_queda_asociada_al_proveedor_que_cobro(sesion, org):
    pago = _pagar(sesion, org, "100")
    guardada = sesion.scalar(select(OrdenPago).where(OrdenPago.id == pago.orden.id))

    assert guardada is not None
    assert guardada.proveedor_id == org.proveedor
    assert guardada.tipo == "OP"


# =========================================================================== contrato HTTP


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


# ⚠️ Estos SÍ commitean (lo hace `get_tenant`), así que van al final y no asumen ningún saldo previo.


def test_el_payload_viejo_de_pagos_sigue_funcionando(cliente_http):
    """El contrato de compatibilidad: el front manda `{proveedor_codigo, monto, fecha}`."""
    r = cliente_http.post(
        "/compras/pagos",
        json={"proveedor_codigo": "PROV-OP", "monto": "150.00", "fecha": None},
    )
    assert r.status_code == 201, r.text


def test_sin_formas_de_pago_la_orden_asume_efectivo(cliente_http):
    r = cliente_http.post("/compras/pagos", json={"proveedor_codigo": "PROV-OP", "monto": "300"})
    assert r.status_code == 201, r.text

    detalle = cliente_http.get(f"/compras/ordenes-pago/{r.json()['documento_id']}").json()
    assert detalle["formas_pago"] == [{"forma": "efectivo", "monto": "300.00"}]


def test_post_con_formas_mixtas_entra(cliente_http):
    r = cliente_http.post(
        "/compras/pagos",
        json={
            "proveedor_codigo": "PROV-OP",
            "monto": "1000",
            "formas_pago": [
                {"forma": "transferencia", "monto": "700"},
                {"forma": "cheque", "monto": "300"},
            ],
        },
    )
    assert r.status_code == 201, r.text

    detalle = cliente_http.get(f"/compras/ordenes-pago/{r.json()['documento_id']}").json()
    assert [f["forma"] for f in detalle["formas_pago"]] == ["transferencia", "cheque"]


def test_la_respuesta_trae_el_documento_emitido(cliente_http):
    """Mismas claves NEUTRAS que la cobranza: el front usa UN schema para las dos solapas."""
    body = cliente_http.post(
        "/compras/pagos", json={"proveedor_codigo": "PROV-OP", "monto": "50"}
    ).json()

    assert set(body) == {
        "movimiento_id",
        "proveedor_id",
        "saldo",
        "documento_id",
        "documento_tipo",
        "documento_pto_venta",
        "documento_numero",
    }
    assert body["documento_tipo"] == "OP"


def test_la_plata_de_las_formas_viaja_como_string(cliente_http):
    r = cliente_http.post(
        "/compras/pagos",
        json={
            "proveedor_codigo": "PROV-OP",
            "monto": "1234.56",
            "formas_pago": [{"forma": "transferencia", "monto": "1234.56"}],
        },
    )
    detalle = cliente_http.get(f"/compras/ordenes-pago/{r.json()['documento_id']}").json()

    assert isinstance(r.json()["saldo"], str)
    assert detalle["total"] == "1234.56"
    assert isinstance(detalle["formas_pago"][0]["monto"], str)


def test_post_con_formas_que_no_suman_es_422(cliente_http):
    r = cliente_http.post(
        "/compras/pagos",
        json={
            "proveedor_codigo": "PROV-OP",
            "monto": "1000",
            "formas_pago": [{"forma": "efectivo", "monto": "999"}],
        },
    )
    assert r.status_code == 422
    assert "suman" in r.json()["detail"]


def test_post_con_una_forma_desconocida_es_422(cliente_http):
    r = cliente_http.post(
        "/compras/pagos",
        json={
            "proveedor_codigo": "PROV-OP",
            "monto": "100",
            "formas_pago": [{"forma": "bitcoin", "monto": "100"}],
        },
    )
    assert r.status_code == 422


def test_get_orden_devuelve_cabecera_y_formas(cliente_http):
    creado = cliente_http.post(
        "/compras/pagos", json={"proveedor_codigo": "PROV-OP", "monto": "80"}
    ).json()

    r = cliente_http.get(f"/compras/ordenes-pago/{creado['documento_id']}")
    assert r.status_code == 200
    body = r.json()
    assert set(body) == {
        "id",
        "proveedor_id",
        "tipo",
        "pto_venta",
        "numero",
        "fecha",
        "total",
        "formas_pago",
    }
    assert body["numero"] == creado["documento_numero"]


def test_get_orden_inexistente_es_404(cliente_http):
    assert cliente_http.get("/compras/ordenes-pago/99999999").status_code == 404


def test_get_orden_de_otra_org_es_404(cliente_http, org):
    assert cliente_http.get(f"/compras/ordenes-pago/{org.orden_vecina}").status_code == 404


def test_la_ruta_de_ordenes_no_se_la_come_la_de_compras(cliente_http):
    """`/compras/ordenes-pago/{id}` va ANTES de `/compras/{compra_id}`. Con el orden invertido,
    FastAPI intentaría leer 'ordenes-pago' como int y daría 422 en vez de 404."""
    r = cliente_http.get("/compras/ordenes-pago/99999999")
    assert r.status_code != 422, (
        "la ruta genérica /compras/{compra_id} se comió /compras/ordenes-pago"
    )
    assert r.status_code == 404


def test_colision_de_numeracion_da_409(cliente_http, monkeypatch):
    monkeypatch.setattr(compras, "asignar_numero", lambda *a, **k: 515151)

    primera = cliente_http.post(
        "/compras/pagos", json={"proveedor_codigo": "PROV-OP", "monto": "10"}
    )
    assert primera.status_code == 201, primera.text

    segunda = cliente_http.post(
        "/compras/pagos", json={"proveedor_codigo": "PROV-OP", "monto": "20"}
    )
    assert segunda.status_code == 409


# =========================================================================== caja y cartera


def test_un_pago_en_efectivo_SALE_de_la_caja(sesion, org):
    """Espejo del lado clientes, con el signo al revés: acá la plata se va del cajón."""
    antes = caja.saldo_efectivo(sesion, org.id)

    _pagar(sesion, org, "1000")

    assert caja.saldo_efectivo(sesion, org.id) == antes - Decimal("1000")


def test_el_cheque_que_firmamos_entra_a_la_cartera_como_EMITIDO(sesion, org):
    """El `origen` no lo elige el caller: lo deduce el service del sentido del dinero.

    Si sale plata, el cheque lo firmamos nosotros. Preguntárselo al caller sería darle la
    oportunidad de contradecir algo que ya dijo al elegir el concepto.
    """
    pago = _pagar(sesion, org, "15000", formas_pago=[compras.FormaPago("cheque", Decimal("15000"))])

    cheques = caja.cheques_de_documento(
        sesion, org.id, ref_tipo=compras.REF_ORDEN_PAGO, ref_id=pago.orden.id
    )
    assert [(c.importe, c.origen, c.estado) for c in cheques] == [
        (Decimal("15000.00"), "emitido", "en_cartera")
    ]


def test_anular_la_orden_revierte_las_tres_cosas(sesion, org):
    saldo_antes = compras.saldo_proveedor(sesion, org.id, org.proveedor)
    caja_antes = caja.saldo_efectivo(sesion, org.id)

    pago = _pagar(
        sesion,
        org,
        "20000",
        formas_pago=[
            compras.FormaPago(EFECTIVO, Decimal("5000")),
            compras.FormaPago("cheque", Decimal("15000")),
        ],
    )
    compras.anular_orden_pago(sesion, org.id, pago.orden.id, motivo="pagado dos veces")

    assert compras.saldo_proveedor(sesion, org.id, org.proveedor) == saldo_antes
    assert caja.saldo_efectivo(sesion, org.id) == caja_antes

    cheques = caja.cheques_de_documento(
        sesion, org.id, ref_tipo=compras.REF_ORDEN_PAGO, ref_id=pago.orden.id
    )
    assert [c.estado for c in cheques] == ["anulado"]
