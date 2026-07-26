"""El recibo de cobranza: que la cobranza emita el documento y lo referencie.

Es el agujero que este módulo vino a tapar. Hasta la 0010 una cobranza escribía un Haber suelto
con `ref_tipo`/`ref_id` en NULL, mientras la venta y la nota de crédito sí referenciaban el suyo.

Lo que no puede faltar:
- Que el movimiento apunte al recibo (`test_la_cobranza_emite_recibo_y_lo_referencia`).
- Que la reversa siga apuntando al MOVIMIENTO y no al recibo: el índice único parcial de la 0009 y
  el EXISTS del extracto asumen que ese `ref_id` es un id de movimiento, y mezclarlos rompería el
  `anulado` en silencio.
- Que el payload viejo del front siga entrando (`test_el_payload_viejo_sigue_funcionando`).
- Que una cobranza ANTERIOR a la 0010, sin recibo, se siga leyendo: es la decisión de no
  backfillear, hecha test.

Dos estilos, como el repo: patrón A (service directo como app_user, sujeto a RLS) y patrón B
(TestClient con JWT) para el contrato HTTP.
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
from app.clientes import service as clientes
from app.core import db as core_db
from app.core.config import get_settings
from app.core.db import ORG_GUC, set_guc
from app.core.models import Miembro, Organizacion
from app.main import app
from app.ventas import service
from app.ventas.models import CtaCteMovimiento, Recibo, ReciboFormaPago
from tests.conftest import APP_URL, OWNER_URL

EFECTIVO = "efectivo"


@pytest.fixture(scope="module")
def org(migrated_db):
    """Una org con un cliente que ya debe plata, más una vecina con su propio recibo."""
    org_id, user_id, vecina_id = uuid4(), uuid4(), uuid4()
    eng = create_engine(OWNER_URL)
    with Session(eng) as s:
        s.add(Organizacion(id=org_id, nombre="Org Recibos"))
        s.add(Organizacion(id=vecina_id, nombre="Org Vecina"))
        s.flush()

        cli = clientes.crear_cliente(s, org_id, codigo="CLI-REC", denominacion="Ferretería Alsina")
        s.add(
            CtaCteMovimiento(
                org_id=org_id,
                cliente_id=cli.id,
                fecha=date(2026, 1, 10),
                tipo="venta",
                debe=Decimal("100000"),
            )
        )

        ajeno = clientes.crear_cliente(s, vecina_id, codigo="CLI-X", denominacion="No Se Ve SA")
        vecino = Recibo(
            org_id=vecina_id,
            cliente_id=ajeno.id,
            tipo="REC",
            pto_venta=1,
            numero=1,
            fecha=date(2026, 5, 1),
            total=Decimal("500"),
        )
        s.add(vecino)
        s.flush()
        s.add(
            ReciboFormaPago(
                org_id=vecina_id, recibo_id=vecino.id, forma=EFECTIVO, monto=Decimal("500")
            )
        )

        s.add(Miembro(org_id=org_id, user_id=user_id, rol="admin"))  # sin esto get_tenant da 403
        s.commit()
        ids = SimpleNamespace(cliente=cli.id, recibo_vecino=vecino.id)
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


def _cobrar(sesion, org, monto: str = "1000", **kw):
    """Cobro en efectivo por el total, que es el caso común."""
    m = Decimal(monto)
    formas = kw.pop("formas_pago", [service.FormaPago(EFECTIVO, m)])
    return service.registrar_cobranza(
        sesion, org.id, cliente_codigo="CLI-REC", monto=m, formas_pago=formas, **kw
    )


# =========================================================================== el recibo


def test_la_cobranza_emite_recibo_y_lo_referencia(sesion, org):
    """EL test de este PR. Antes el movimiento salía con ref_tipo/ref_id en NULL."""
    cobranza = _cobrar(sesion, org, "1000")

    assert cobranza.recibo.id is not None
    assert cobranza.movimiento.ref_tipo == "recibo"
    assert cobranza.movimiento.ref_id == cobranza.recibo.id
    assert cobranza.recibo.total == Decimal("1000")
    assert cobranza.movimiento.haber == Decimal("1000")


def test_el_recibo_numera_correlativo_por_punto_de_venta(sesion, org):
    """El numerador es por (tipo, punto de venta): dos mostradores no comparten contador."""
    assert _cobrar(sesion, org, "10").recibo.numero == 1
    assert _cobrar(sesion, org, "20").recibo.numero == 2
    assert _cobrar(sesion, org, "30", pto_venta=2).recibo.numero == 1
    assert _cobrar(sesion, org, "40").recibo.numero == 3


def test_el_recibo_no_comparte_numerador_con_las_facturas(sesion, org):
    """Si compartieran contador, el primer recibo de una org que ya facturó saldría con un número
    salteado y sin explicación para el cliente que lo recibe."""
    for _ in range(5):
        service.asignar_numero(sesion, org.id, tipo="FAC", pto_venta=1)

    assert _cobrar(sesion, org, "10").recibo.numero == 1


def test_un_pago_mixto_deja_dos_renglones(sesion, org):
    """El caso que justifica que el detalle sea 1:N: efectivo + cheque en el mismo cobro."""
    cobranza = _cobrar(
        sesion,
        org,
        "20000",
        formas_pago=[
            service.FormaPago(EFECTIVO, Decimal("5000")),
            service.FormaPago("cheque", Decimal("15000")),
        ],
    )

    formas = service.formas_de_recibo(sesion, org.id, cobranza.recibo.id)
    assert [(f.forma, f.monto) for f in formas] == [
        (EFECTIVO, Decimal("5000")),
        ("cheque", Decimal("15000")),
    ]


def test_el_recibo_hereda_la_fecha_de_la_cobranza(sesion, org):
    """La plata del viernes cargada el lunes: el recibo se fecha con el movimiento, no con el alta.
    `creado_en` guarda igual el momento real, así que el retroactivo queda auditable."""
    cobranza = _cobrar(sesion, org, "500", fecha=date(2026, 2, 20))

    assert cobranza.recibo.fecha == date(2026, 2, 20)
    assert cobranza.movimiento.fecha == date(2026, 2, 20)
    assert cobranza.recibo.creado_en.date() >= date(2026, 7, 25)


def test_el_recibo_y_el_movimiento_comparten_creado_por(sesion, org):
    usuario = uuid4()
    cobranza = _cobrar(sesion, org, "500", usuario_id=usuario)

    assert cobranza.recibo.creado_por == usuario
    assert cobranza.movimiento.creado_por == usuario


def test_dos_cobranzas_no_comparten_recibo(sesion, org):
    a = _cobrar(sesion, org, "100")
    b = _cobrar(sesion, org, "200")

    assert a.recibo.id != b.recibo.id
    assert a.movimiento.ref_id != b.movimiento.ref_id


# =========================================================================== lo que NO entra


def test_formas_que_no_suman_el_total_no_entran(sesion, org):
    with pytest.raises(service.VentaInvalida, match="suman"):
        _cobrar(sesion, org, "1000", formas_pago=[service.FormaPago(EFECTIVO, Decimal("999.99"))])


def test_formas_vacias_no_entran(sesion, org):
    """El service exige el dato aunque el borde HTTP lo asuma: el importador de Paradox entra por
    acá y SÍ tiene el detalle real."""
    with pytest.raises(service.VentaInvalida, match="con qué se cobró"):
        _cobrar(sesion, org, "1000", formas_pago=[])


def test_una_forma_inventada_no_entra(sesion, org):
    with pytest.raises(service.VentaInvalida, match="desconocida"):
        _cobrar(sesion, org, "1000", formas_pago=[service.FormaPago("bitcoin", Decimal("1000"))])


def test_un_renglon_en_cero_no_entra(sesion, org):
    with pytest.raises(service.VentaInvalida, match="mayor a cero"):
        _cobrar(
            sesion,
            org,
            "1000",
            formas_pago=[
                service.FormaPago(EFECTIVO, Decimal("1000")),
                service.FormaPago("cheque", Decimal("0")),
            ],
        )


def test_una_cobranza_en_cero_no_entra(sesion, org):
    with pytest.raises(service.VentaInvalida, match="mayor a cero"):
        _cobrar(sesion, org, "0")


def test_un_cliente_inexistente_no_emite_recibo(sesion, org):
    """Y NO tiene que haber consumido un número de recibo: el cliente se resuelve antes de numerar."""
    with pytest.raises(service.VentaInvalida, match="No existe el cliente"):
        service.registrar_cobranza(
            sesion,
            org.id,
            cliente_codigo="NO-EXISTE",
            monto=Decimal("100"),
            formas_pago=[service.FormaPago(EFECTIVO, Decimal("100"))],
        )

    assert _cobrar(sesion, org, "100").recibo.numero == 1


# =========================================================================== recibo vs. ajuste


def test_anular_una_cobranza_no_borra_su_recibo(sesion, org):
    """El recibo es papel entregado: se revierte su EFECTO, el documento queda vivo.

    Sigue sin haber columna `anulado` en `recibos`, y no es un olvido: el estado queda DERIVADO de
    que existe una reversa del movimiento que lo referencia. Una fila menos que desincronizar.
    """
    cobranza = _cobrar(sesion, org, "1000")
    service.anular_recibo(sesion, org.id, cobranza.recibo.id, motivo="cobré de más")

    assert service.obtener_recibo(sesion, org.id, cobranza.recibo.id) is not None


def test_la_reversa_apunta_al_movimiento_y_no_al_recibo(sesion, org):
    """Si apuntara al recibo, ids de dos tablas competirían en el mismo espacio del índice único
    parcial de la 0009 y el `anulado` del extracto se rompería EN SILENCIO."""
    cobranza = _cobrar(sesion, org, "1000")
    reversa = service.anular_recibo(sesion, org.id, cobranza.recibo.id, motivo="cobré de más")

    assert (reversa.ref_tipo, reversa.ref_id) == ("ajuste_de", cobranza.movimiento.id)


def test_una_cobranza_YA_NO_se_revierte_desde_el_extracto(sesion, org):
    """El cambio que trajo `app/caja/`, hecho test.

    Mientras el recibo no movía nada fuera del ledger, revertir el Haber cancelaba el 100% de su
    efecto. Desde que mueve caja y cartera, revertir solo el ledger dejaría esas dos cosas vivas —
    el pecado que este diseño existe para no repetir. La anulación correcta es `anular_recibo`.
    """
    cobranza = _cobrar(sesion, org, "1000")

    filas, _ = service.movimientos_cliente(sesion, org.id, org.cliente, limite=100)
    fila = next(f for f in filas if f.id == cobranza.movimiento.id)
    assert fila.reversible is False
    assert fila.anulado is False

    with pytest.raises(service.VentaInvalida, match="no se revierte desde la cuenta corriente"):
        service.registrar_ajuste(
            sesion,
            org.id,
            cliente_id=org.cliente,
            motivo="por izquierda",
            revierte_movimiento_id=cobranza.movimiento.id,
        )


def test_el_extracto_muestra_la_referencia_de_la_cobranza(sesion, org):
    """La columna "Referencia" del extracto dejaba de estar vacía justo acá."""
    cobranza = _cobrar(sesion, org, "1000")

    filas, _ = service.movimientos_cliente(sesion, org.id, org.cliente, limite=100)
    fila = next(f for f in filas if f.id == cobranza.movimiento.id)
    assert (fila.ref_tipo, fila.ref_id) == ("recibo", cobranza.recibo.id)


def test_una_cobranza_vieja_sin_recibo_sigue_leyendose(sesion, org):
    """La decisión de NO backfillear, hecha test.

    Las cobranzas anteriores a la 0010 tienen la referencia en NULL y se quedan así: un recibo
    retroactivo sería un documento falsificado. El extracto tiene que seguir andando con ellas.
    """
    vieja = CtaCteMovimiento(
        org_id=org.id,
        cliente_id=org.cliente,
        fecha=date(2026, 3, 1),
        tipo="cobranza",
        haber=Decimal("777"),
    )
    sesion.add(vieja)
    sesion.flush()

    filas, _ = service.movimientos_cliente(sesion, org.id, org.cliente, limite=100)
    fila = next(f for f in filas if f.id == vieja.id)
    assert fila.ref_tipo is None
    assert fila.ref_id is None
    # Tampoco es reversible desde el extracto: 'cobranza' salió de MOVIMIENTOS_REVERSIBLES para
    # TODAS, viejas incluidas. Estas no tienen recibo que anular, así que se corrigen con un
    # ajuste MANUAL, que deja el motivo escrito.
    assert fila.reversible is False


# =========================================================================== lecturas


def test_obtener_recibo_de_otra_org_es_none(sesion, org):
    assert service.obtener_recibo(sesion, org.id, org.recibo_vecino) is None


def test_formas_de_un_recibo_ajeno_no_se_ven(sesion, org):
    assert service.formas_de_recibo(sesion, org.id, org.recibo_vecino) == []


def test_el_recibo_queda_asociado_al_cliente_que_pago(sesion, org):
    cobranza = _cobrar(sesion, org, "100")
    guardado = sesion.scalar(select(Recibo).where(Recibo.id == cobranza.recibo.id))

    assert guardado is not None
    assert guardado.cliente_id == org.cliente
    assert guardado.tipo == "REC"


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


# ⚠️ Estos SÍ commitean (lo hace `get_tenant`), así que van al final del archivo y no asumen
# ningún saldo previo — el de arriba ya lo movieron los tests de service.


def test_el_payload_viejo_sigue_funcionando(cliente_http):
    """El front manda `{cliente_codigo, monto, fecha}` y tiene que seguir entrando.

    Es lo que permite desplegar este PR sin el del frontend.
    """
    r = cliente_http.post(
        "/ventas/cobranzas",
        json={"cliente_codigo": "CLI-REC", "monto": "150.00", "fecha": None},
    )
    assert r.status_code == 201, r.text


def test_sin_formas_de_pago_el_recibo_asume_efectivo(cliente_http):
    r = cliente_http.post("/ventas/cobranzas", json={"cliente_codigo": "CLI-REC", "monto": "300"})
    assert r.status_code == 201, r.text

    detalle = cliente_http.get(f"/ventas/recibos/{r.json()['documento_id']}").json()
    assert detalle["formas_pago"] == [{"forma": "efectivo", "monto": "300.00"}]


def test_post_con_formas_mixtas_entra(cliente_http):
    r = cliente_http.post(
        "/ventas/cobranzas",
        json={
            "cliente_codigo": "CLI-REC",
            "monto": "1000",
            "formas_pago": [
                {"forma": "efectivo", "monto": "400"},
                {"forma": "cheque", "monto": "600"},
            ],
        },
    )
    assert r.status_code == 201, r.text

    detalle = cliente_http.get(f"/ventas/recibos/{r.json()['documento_id']}").json()
    assert [f["forma"] for f in detalle["formas_pago"]] == ["efectivo", "cheque"]


def test_la_respuesta_trae_el_documento_emitido(cliente_http):
    r = cliente_http.post("/ventas/cobranzas", json={"cliente_codigo": "CLI-REC", "monto": "50"})
    body = r.json()

    assert set(body) == {
        "movimiento_id",
        "cliente_id",
        "saldo",
        "documento_id",
        "documento_tipo",
        "documento_pto_venta",
        "documento_numero",
    }
    assert body["documento_tipo"] == "REC"
    assert isinstance(body["documento_numero"], int)


def test_la_plata_de_las_formas_viaja_como_string(cliente_http):
    """Igual que el resto del dominio: los Decimal salen como str para que el front no los pase
    por float. Extiende lo que fija `test_plata_viaja_como_string` en test_cta_cte.py."""
    r = cliente_http.post(
        "/ventas/cobranzas",
        json={
            "cliente_codigo": "CLI-REC",
            "monto": "1234.56",
            "formas_pago": [{"forma": "transferencia", "monto": "1234.56"}],
        },
    )
    detalle = cliente_http.get(f"/ventas/recibos/{r.json()['documento_id']}").json()

    assert isinstance(r.json()["saldo"], str)
    assert detalle["total"] == "1234.56"
    assert isinstance(detalle["formas_pago"][0]["monto"], str)


def test_post_con_formas_que_no_suman_es_422(cliente_http):
    r = cliente_http.post(
        "/ventas/cobranzas",
        json={
            "cliente_codigo": "CLI-REC",
            "monto": "1000",
            "formas_pago": [{"forma": "efectivo", "monto": "999"}],
        },
    )
    assert r.status_code == 422
    assert "suman" in r.json()["detail"]


def test_post_con_una_forma_desconocida_es_422(cliente_http):
    """Lo rechaza el `Literal` de Pydantic, antes de llegar al service."""
    r = cliente_http.post(
        "/ventas/cobranzas",
        json={
            "cliente_codigo": "CLI-REC",
            "monto": "100",
            "formas_pago": [{"forma": "bitcoin", "monto": "100"}],
        },
    )
    assert r.status_code == 422


def test_get_recibo_devuelve_cabecera_y_formas(cliente_http):
    creado = cliente_http.post(
        "/ventas/cobranzas", json={"cliente_codigo": "CLI-REC", "monto": "80"}
    ).json()

    r = cliente_http.get(f"/ventas/recibos/{creado['documento_id']}")
    assert r.status_code == 200
    body = r.json()
    assert set(body) == {
        "id",
        "cliente_id",
        "tipo",
        "pto_venta",
        "numero",
        "fecha",
        "total",
        "formas_pago",
    }
    assert body["numero"] == creado["documento_numero"]


def test_get_recibo_inexistente_es_404(cliente_http):
    assert cliente_http.get("/ventas/recibos/99999999").status_code == 404


def test_get_recibo_de_otra_org_es_404(cliente_http, org):
    """404 y no 403: no se le confirma a nadie que ese id existe en otro tenant."""
    assert cliente_http.get(f"/ventas/recibos/{org.recibo_vecino}").status_code == 404


def test_la_ruta_de_recibos_no_se_la_come_la_de_ventas(cliente_http):
    """`/ventas/recibos/{id}` está declarada ANTES de `/ventas/{venta_id}`.

    Con el orden invertido, FastAPI entraría por la ruta genérica e intentaría leer 'recibos' como
    int: daría 422 (error de validación del path) en vez del 404 que corresponde. Por eso el assert
    es sobre el 422 y no sobre el 404 — es lo que distingue las dos situaciones.
    """
    r = cliente_http.get("/ventas/recibos/99999999")
    assert r.status_code != 422, "la ruta genérica /ventas/{venta_id} se comió /ventas/recibos"
    assert r.status_code == 404


def test_colision_de_numeracion_da_409(cliente_http, monkeypatch):
    """Dos cajas cobrando a la vez. El lock del numerador las serializa, pero si igual chocan el
    unique del recibo es el árbitro, y eso sale como 409 (no como 500)."""
    monkeypatch.setattr(service, "asignar_numero", lambda *a, **k: 424242)

    primera = cliente_http.post(
        "/ventas/cobranzas", json={"cliente_codigo": "CLI-REC", "monto": "10"}
    )
    assert primera.status_code == 201, primera.text

    segunda = cliente_http.post(
        "/ventas/cobranzas", json={"cliente_codigo": "CLI-REC", "monto": "20"}
    )
    assert segunda.status_code == 409


# =========================================================================== caja y cartera


def test_un_cobro_en_efectivo_entra_a_la_caja(sesion, org):
    """EL test de este PR. Antes el saldo del cliente bajaba y el dinero no aparecía en ningún
    lado: la cobranza no tenía efecto fuera del ledger."""
    antes = caja.saldo_efectivo(sesion, org.id)

    _cobrar(sesion, org, "1000")

    assert caja.saldo_efectivo(sesion, org.id) == antes + Decimal("1000")


def test_un_pago_mixto_reparte_entre_caja_y_cartera(sesion, org):
    """El caso que justifica que el detalle de formas sea 1:N, ahora con consecuencias.

    5.000 en efectivo + 15.000 en cheque NO son 20.000 en el cajón: son 5.000 en el cajón y un
    papel de 15.000 en la cartera. Confundirlos es exactamente el error que el módulo evita.
    """
    antes = caja.saldo_efectivo(sesion, org.id)

    cobranza = _cobrar(
        sesion,
        org,
        "20000",
        formas_pago=[
            service.FormaPago(EFECTIVO, Decimal("5000")),
            service.FormaPago("cheque", Decimal("15000")),
        ],
    )

    assert caja.saldo_efectivo(sesion, org.id) == antes + Decimal("5000")

    cheques = caja.cheques_de_documento(
        sesion, org.id, ref_tipo=service.REF_RECIBO, ref_id=cobranza.recibo.id
    )
    assert [(c.importe, c.origen, c.estado) for c in cheques] == [
        (Decimal("15000.00"), "recibido", "en_cartera")
    ]


def test_los_movimientos_de_caja_referencian_al_recibo(sesion, org):
    """Sin la referencia no habría forma de anular: la anulación busca por (ref_tipo, ref_id)."""
    cobranza = _cobrar(sesion, org, "1000")

    filas, _ = caja.movimientos(sesion, org.id)
    del_recibo = [f for f in filas if f.ref_id == cobranza.recibo.id and f.ref_tipo == "recibo"]

    assert len(del_recibo) == 1
    assert del_recibo[0].concepto == "cobranza"
    assert del_recibo[0].ingreso == Decimal("1000.00")


def test_anular_revierte_las_tres_cosas_a_la_vez(sesion, org):
    """La razón de que `anular_recibo` exista y de que 'cobranza' saliera de REVERSIBLES.

    Revertir solo el ledger dejaría la caja con la plata y el cheque en la cartera: el sistema
    diría que el cliente sigue debiendo Y que tenemos su dinero. Las tres reversas van juntas.
    """
    saldo_cta_antes = service.saldo_cliente(sesion, org.id, org.cliente)
    caja_antes = caja.saldo_efectivo(sesion, org.id)

    cobranza = _cobrar(
        sesion,
        org,
        "20000",
        formas_pago=[
            service.FormaPago(EFECTIVO, Decimal("5000")),
            service.FormaPago("cheque", Decimal("15000")),
        ],
    )
    service.anular_recibo(sesion, org.id, cobranza.recibo.id, motivo="cargada dos veces")

    assert service.saldo_cliente(sesion, org.id, org.cliente) == saldo_cta_antes
    assert caja.saldo_efectivo(sesion, org.id) == caja_antes

    cheques = caja.cheques_de_documento(
        sesion, org.id, ref_tipo=service.REF_RECIBO, ref_id=cobranza.recibo.id
    )
    assert [c.estado for c in cheques] == ["anulado"]


def test_no_se_puede_anular_si_el_cheque_ya_se_movio(sesion, org):
    """La reja que evita que la cartera y el banco digan cosas distintas.

    Si el cheque ya se depositó, el dinero siguió su camino fuera de este documento. Deshacerlo
    desde acá dejaría la cartera limpia y el banco con un depósito que nadie explica.
    """
    cobranza = _cobrar(
        sesion, org, "15000", formas_pago=[service.FormaPago("cheque", Decimal("15000"))]
    )
    cheques = caja.cheques_de_documento(
        sesion, org.id, ref_tipo=service.REF_RECIBO, ref_id=cobranza.recibo.id
    )
    cheques[0].estado = "depositado"
    sesion.flush()

    with pytest.raises(service.VentaInvalida, match="cheques que ya se movieron"):
        service.anular_recibo(sesion, org.id, cobranza.recibo.id, motivo="tarde")


def test_anular_dos_veces_el_mismo_recibo_se_rechaza(sesion, org):
    cobranza = _cobrar(sesion, org, "1000")
    service.anular_recibo(sesion, org.id, cobranza.recibo.id, motivo="primera")

    with pytest.raises(service.VentaInvalida, match="ya fue anulado"):
        service.anular_recibo(sesion, org.id, cobranza.recibo.id, motivo="segunda")


def test_la_anulacion_necesita_motivo(sesion, org):
    cobranza = _cobrar(sesion, org, "1000")

    with pytest.raises(service.VentaInvalida, match="necesita un motivo"):
        service.anular_recibo(sesion, org.id, cobranza.recibo.id, motivo="   ")
