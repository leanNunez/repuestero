"""Cartera de cheques: el ciclo de vida del papel y lo que mueve de plata.

Dos patrones, como el resto de la suite:
- Patrón A (service contra Postgres con `app_user`): la máquina de estados y la aritmética.
- Patrón B (TestClient con JWT): el contrato HTTP, incluidos el 404 y el 422.

Lo que no puede faltar:
- **Que cobrar un cheque no duplique la plata.** Es el bug que motivó la migración 0012: sin la
  pata de egreso, la caja diría que tiene el cheque Y el dinero.
- Que la forma en que acredita dependa del CAMINO (ventanilla = efectivo, banco = transferencia),
  para que `saldo_efectivo` siga siendo arqueable contra el cajón.
- Que un cheque EMITIDO no vuelva a mover caja: su plata ya salió con la orden de pago.
- Que las transiciones inválidas no pasen, incluida la salida de `anulado`.
"""

from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from types import SimpleNamespace
from uuid import uuid4

import jwt
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.caja import service
from app.caja.models import Cheque
from app.core import db as core_db
from app.core.config import get_settings
from app.core.db import ORG_GUC, set_guc
from app.core.models import Miembro, Organizacion
from app.main import app
from tests.conftest import APP_URL, OWNER_URL

IMPORTE = Decimal("15000")


@pytest.fixture(scope="module")
def org(migrated_db):
    org_id, vecina_id, user_id = uuid4(), uuid4(), uuid4()
    eng = create_engine(OWNER_URL)
    with Session(eng) as s:
        s.add(Organizacion(id=org_id, nombre="Org Cartera"))
        s.add(Organizacion(id=vecina_id, nombre="Org Vecina Cartera"))
        s.flush()
        set_guc(s, ORG_GUC, str(org_id))
        s.add(Miembro(org_id=org_id, user_id=user_id, rol="admin"))
        s.commit()
    eng.dispose()
    return SimpleNamespace(id=org_id, user=user_id, vecina=vecina_id)


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


def _cobrar_con_cheque(sesion, org, *, ref_id: int = 1, importe: Decimal = IMPORTE) -> Cheque:
    """Un recibo cobrado con un cheque. Es como nace un cheque de verdad, así que los tests parten
    del mismo estado que produce el sistema en vez de insertar la fila a mano."""
    asiento = service.asentar_documento(
        sesion,
        org.id,
        concepto="cobranza",
        ref_tipo="recibo",
        ref_id=ref_id,
        formas=[("cheque", importe)],
    )
    return asiento.cheques[0]


def _pagar_con_cheque(sesion, org, *, ref_id: int = 1) -> Cheque:
    """Una orden de pago cancelada con un cheque propio: nace `emitido`."""
    asiento = service.asentar_documento(
        sesion,
        org.id,
        concepto="pago_proveedor",
        ref_tipo="orden_pago",
        ref_id=ref_id,
        formas=[("cheque", IMPORTE)],
    )
    return asiento.cheques[0]


# =========================================================================== el bug de la 0012


def test_cobrar_un_cheque_no_duplica_la_plata(sesion, org):
    """EL test de este PR.

    Sin la pata de egreso (`cheque_cobrado_cartera`), la caja quedaría diciendo
    `cheque=15000` + `efectivo=15000` = 30.000 cuando en el negocio hay 15.000. El cheque tiene que
    SALIR de la cartera cuando entra la plata.
    """
    cheque = _cobrar_con_cheque(sesion, org)
    assert service.saldo_por_forma(sesion, org.id)["cheque"] == IMPORTE

    service.cobrar(sesion, org.id, cheque.id)

    saldos = service.saldo_por_forma(sesion, org.id)
    assert saldos["cheque"] == Decimal("0"), "el cheque tiene que salir de la cartera"
    assert saldos["efectivo"] == IMPORTE
    assert sum(saldos.values()) == IMPORTE, "la plata no se duplica"


def test_cobrar_escribe_las_dos_patas(sesion, org):
    """Un solo hecho, dos filas: el papel sale y la plata entra. Ver `conceptos_caja`."""
    cheque = _cobrar_con_cheque(sesion, org)

    asiento = service.cobrar(sesion, org.id, cheque.id)

    escritos = {(m.concepto, m.forma) for m in asiento.movimientos}
    assert escritos == {("cheque_cobrado_cartera", "cheque"), ("cheque_cobrado", "efectivo")}
    # Y las dos referencian al papel que las causó, que es lo que hace auditable el extracto.
    assert all(m.ref_tipo == "cheque" and m.ref_id == cheque.id for m in asiento.movimientos)


# =========================================================================== la forma según el camino


def test_cobrado_por_ventanilla_entra_al_cajon(sesion, org):
    """`en_cartera -> cobrado`: lo cobré en la ventanilla, la plata está en el cajón."""
    cheque = _cobrar_con_cheque(sesion, org)

    service.cobrar(sesion, org.id, cheque.id)

    assert service.saldo_efectivo(sesion, org.id) == IMPORTE


def test_cobrado_despues_de_depositar_entra_como_transferencia(sesion, org):
    """`depositado -> cobrado`: lo acreditó el BANCO. Si esto sumara al efectivo, `saldo_efectivo`
    diría que hay plata en el cajón que en realidad está en el banco, y dejaría de ser arqueable
    contra lo que se cuenta a mano — que es todo lo que promete."""
    cheque = _cobrar_con_cheque(sesion, org)
    service.depositar(sesion, org.id, cheque.id)

    service.cobrar(sesion, org.id, cheque.id)

    saldos = service.saldo_por_forma(sesion, org.id)
    assert saldos["efectivo"] == Decimal("0"), "el cajón no recibió nada"
    assert saldos["transferencia"] == IMPORTE
    assert saldos["cheque"] == Decimal("0")


# =========================================================================== las otras transiciones


def test_depositar_no_mueve_plata(sesion, org):
    """El cheque cambió de lugar físico, no de valor: sigue valiendo lo mismo en la cartera."""
    cheque = _cobrar_con_cheque(sesion, org)

    asiento = service.depositar(sesion, org.id, cheque.id)

    assert asiento.movimientos == []
    assert cheque.estado == "depositado"
    assert service.saldo_por_forma(sesion, org.id)["cheque"] == IMPORTE


def test_rechazar_saca_de_la_cartera_sin_acreditar_nada(sesion, org):
    """El banco lo devolvió: el valor nunca existió. La deuda del cliente revive por el lado de la
    cuenta corriente, no acá."""
    cheque = _cobrar_con_cheque(sesion, org)

    asiento = service.rechazar(sesion, org.id, cheque.id)

    saldos = service.saldo_por_forma(sesion, org.id)
    assert saldos["cheque"] == Decimal("0")
    assert saldos["efectivo"] == Decimal("0")
    assert [(m.concepto, m.forma) for m in asiento.movimientos] == [("cheque_rechazado", "cheque")]


def test_entregar_endosa_el_cheque_como_pago_a_proveedor(sesion, org):
    cheque = _cobrar_con_cheque(sesion, org)

    asiento = service.entregar(sesion, org.id, cheque.id)

    assert cheque.estado == "entregado"
    assert [(m.concepto, m.forma) for m in asiento.movimientos] == [("pago_proveedor", "cheque")]
    assert service.saldo_por_forma(sesion, org.id)["cheque"] == Decimal("0")


# =========================================================================== el cheque emitido


def test_un_cheque_emitido_cambia_de_estado_sin_tocar_la_caja(sesion, org):
    """Cuando se registró la orden de pago la plata YA salió. Volver a escribir un egreso al
    entregarle el papel al proveedor haría que el mismo pago salga dos veces."""
    cheque = _pagar_con_cheque(sesion, org)
    saldo_tras_emitir = service.saldo_por_forma(sesion, org.id)["cheque"]

    asiento = service.entregar(sesion, org.id, cheque.id)

    assert cheque.estado == "entregado"
    assert asiento.movimientos == [], "un emitido no vuelve a mover caja"
    assert service.saldo_por_forma(sesion, org.id)["cheque"] == saldo_tras_emitir


def test_un_cheque_emitido_nace_con_origen_emitido(sesion, org):
    """El origen no se pide: lo dice el concepto. Si entra plata me lo dieron, si sale lo firmé."""
    assert _pagar_con_cheque(sesion, org).origen == "emitido"
    assert _cobrar_con_cheque(sesion, org, ref_id=2).origen == "recibido"


# =========================================================================== transiciones inválidas


@pytest.mark.parametrize(
    ("camino", "prohibida"),
    [
        # Un terminal no vuelve: la plata ya siguió su camino.
        (("cobrar",), "cobrar"),
        (("cobrar",), "rechazar"),
        (("entregar",), "depositar"),
        (("rechazar",), "cobrar"),
        # El papel ya está en el banco: no se puede endosar lo que no tenés en la mano.
        (("depositar",), "entregar"),
    ],
)
def test_una_transicion_invalida_no_pasa(sesion, org, camino, prohibida):
    cheque = _cobrar_con_cheque(sesion, org)
    for paso in camino:
        getattr(service, paso)(sesion, org.id, cheque.id)

    with pytest.raises(service.CajaInvalida, match="no puede pasar a"):
        getattr(service, prohibida)(sesion, org.id, cheque.id)


def test_un_cheque_anulado_no_resucita(sesion, org):
    """`anulado` es terminal. Lo deja ahí `revertir_documento` cuando se anula el recibo, y no hay
    arista de salida: un cheque cuyo documento se dio de baja no se puede cobrar."""
    cheque = _cobrar_con_cheque(sesion, org)
    service.revertir_documento(
        sesion, org.id, concepto="anulacion_cobranza", ref_tipo="recibo", ref_id=1
    )
    assert cheque.estado == "anulado"

    with pytest.raises(service.CajaInvalida, match="es un estado final"):
        service.cobrar(sesion, org.id, cheque.id)


def test_una_transicion_sobre_un_cheque_inexistente_no_es_un_error_de_negocio(sesion, org):
    """404, no 422: "no existe" y "no se puede" son respuestas distintas. Confundirlas fue el bug
    de `GET /ventas/clientes/{id}/saldo` (PR #47)."""
    with pytest.raises(service.ChequeNoEncontrado):
        service.cobrar(sesion, org.id, 999_999)


# =========================================================================== conciliación


def test_conciliar_marca_el_cheque_con_su_fecha(sesion, org):
    cheque = _cobrar_con_cheque(sesion, org)
    service.cobrar(sesion, org.id, cheque.id)

    service.conciliar(sesion, org.id, cheque.id, fecha=date(2026, 3, 20))

    assert cheque.conciliado is True
    assert cheque.fecha_conciliacion == date(2026, 3, 20)
    # Conciliar es ORTOGONAL al estado: no lo mueve.
    assert cheque.estado == "cobrado"


def test_conciliar_dos_veces_no_pasa(sesion, org):
    cheque = _cobrar_con_cheque(sesion, org)
    service.cobrar(sesion, org.id, cheque.id)
    service.conciliar(sesion, org.id, cheque.id, fecha=date(2026, 3, 20))

    with pytest.raises(service.CajaInvalida, match="ya estaba conciliado"):
        service.conciliar(sesion, org.id, cheque.id, fecha=date(2026, 3, 21))


@pytest.mark.parametrize("transicion", ["depositar", "cobrar", "rechazar"])
def test_se_concilia_lo_que_paso_por_el_banco(sesion, org, transicion):
    cheque = _cobrar_con_cheque(sesion, org)
    getattr(service, transicion)(sesion, org.id, cheque.id)

    service.conciliar(sesion, org.id, cheque.id, fecha=date(2026, 3, 20))

    assert cheque.conciliado is True


def test_un_cheque_en_cartera_no_se_concilia(sesion, org):
    """Está en tu mano, no en el banco: no puede figurar en ningún resumen todavía."""
    cheque = _cobrar_con_cheque(sesion, org)

    with pytest.raises(service.CajaInvalida, match="no pasó por el banco"):
        service.conciliar(sesion, org.id, cheque.id, fecha=date(2026, 3, 20))


def test_un_cheque_anulado_no_se_concilia(sesion, org):
    """El bug que destapó probar la pantalla: la cartera ofrecía "Conciliar" en un cheque anulado.

    Un cheque cuyo documento se dio de baja **nunca existió para el banco**, así que cruzarlo contra
    el resumen es pedir una operación imposible.
    """
    cheque = _cobrar_con_cheque(sesion, org)
    service.revertir_documento(
        sesion, org.id, concepto="anulacion_cobranza", ref_tipo="recibo", ref_id=1
    )

    with pytest.raises(service.CajaInvalida, match="no pasó por el banco"):
        service.conciliar(sesion, org.id, cheque.id, fecha=date(2026, 3, 20))


def test_un_cheque_entregado_no_se_concilia(sesion, org):
    """Se lo diste a un proveedor: entra al banco de OTRO, no al tuyo."""
    cheque = _cobrar_con_cheque(sesion, org)
    service.entregar(sesion, org.id, cheque.id)

    with pytest.raises(service.CajaInvalida, match="no pasó por el banco"):
        service.conciliar(sesion, org.id, cheque.id, fecha=date(2026, 3, 20))


# =========================================================================== listado


def test_la_cartera_se_filtra_por_estado(sesion, org):
    uno = _cobrar_con_cheque(sesion, org, ref_id=1)
    _cobrar_con_cheque(sesion, org, ref_id=2)
    service.depositar(sesion, org.id, uno.id)

    depositados, total = service.cartera(sesion, org.id, estado="depositado")

    assert total == 1
    assert [c.id for c in depositados] == [uno.id]


def test_el_valor_en_cartera_cuenta_solo_los_que_estan_en_la_mano(sesion, org):
    """Con SOLO cheques recibidos, el inventario del papel y el libro del dinero coinciden: cada
    recibido entra con +importe y sale con -importe."""
    uno = _cobrar_con_cheque(sesion, org, ref_id=1)
    _cobrar_con_cheque(sesion, org, ref_id=2, importe=Decimal("5000"))
    service.cobrar(sesion, org.id, uno.id)

    assert service.valor_en_cartera(sesion, org.id) == Decimal("5000")
    assert service.saldo_por_forma(sesion, org.id)["cheque"] == Decimal("5000")


def test_un_cheque_EMITIDO_separa_la_cartera_del_neto_del_libro(sesion, org):
    """El invariante que faltaba, y que probar el circuito completo destapó.

    Una versión anterior del código afirmaba que `valor_en_cartera` y `saldo['cheque']` "tienen que
    coincidir" y que eso era un arqueo. **Es falso en cuanto hay cheques emitidos**: un cheque
    propio escribe un egreso sin contrapartida —no entra a la cartera, sale del bolsillo— así que:

        saldo['cheque']  ==  valor_en_cartera  -  (suma de los emitidos)

    Con la afirmación vieja, un arqueo construido sobre esa igualdad daba falso positivo para
    siempre. Y la pantalla mostraba ese neto rotulado "Cheques en cartera".
    """
    _cobrar_con_cheque(sesion, org, ref_id=1, importe=Decimal("10000"))
    _pagar_con_cheque(sesion, org, ref_id=2)  # emitido por 15.000

    en_cartera = service.valor_en_cartera(sesion, org.id)
    neto_libro = service.saldo_por_forma(sesion, org.id)["cheque"]

    # Lo que tengo en la mano: SOLO el recibido. El emitido también nace `en_cartera`, pero no es
    # un activo mío — es un papel que voy a tener que pagar.
    assert en_cartera == Decimal("10000")
    # El neto del libro resta el emitido, y puede quedar NEGATIVO sin que nada esté mal.
    assert neto_libro == Decimal("10000") - IMPORTE
    assert neto_libro < 0
    assert neto_libro == en_cartera - IMPORTE


def test_un_cheque_emitido_sin_entregar_no_infla_la_cartera(sesion, org):
    """Nace `en_cartera` como cualquiera, pero no es plata que tengo: es plata que debo."""
    _pagar_con_cheque(sesion, org, ref_id=1)

    assert service.valor_en_cartera(sesion, org.id) == Decimal("0")


def test_el_neto_de_cheques_en_negativo_NO_dispara_advertencia(sesion, org):
    """La otra cara del mismo bug: tener cheques propios en la calle es lo NORMAL.

    Si la advertencia mirara `saldo['cheque']`, gritaría en cuanto firmás más de los que tenés — y
    una alarma que suena siempre es una alarma que nadie mira. La cantidad que de verdad no puede
    ser negativa del lado de los cheques es `valor_en_cartera`, y lo es por construcción.
    """
    _pagar_con_cheque(sesion, org, ref_id=1)

    assert service.saldo_por_forma(sesion, org.id)["cheque"] < 0
    assert service.advertencias_de_saldo(sesion, org.id) == []
    assert service.advertencias_de_saldo(sesion, org.id, formas=["cheque"]) == []


def test_el_efectivo_en_negativo_SIGUE_advirtiendo(sesion, org):
    """El recorte es SOLO para cheques: el cajón no puede tener menos que cero."""
    service.registrar_movimiento(
        sesion, org.id, concepto="gasto", forma="efectivo", monto=Decimal("100")
    )

    assert len(service.advertencias_de_saldo(sesion, org.id)) == 1


def test_los_cheques_sin_fecha_de_cobro_van_al_final(sesion, org):
    """La pregunta del mostrador es "qué puedo depositar esta semana": los que tienen fecha van
    primero, y los que nadie completó todavía quedan al final en vez de encabezar la lista."""
    sin_fecha = _cobrar_con_cheque(sesion, org, ref_id=1)
    con_fecha = _cobrar_con_cheque(sesion, org, ref_id=2)
    con_fecha.fecha_cobro = date(2026, 4, 1)
    sesion.flush()

    cheques, _ = service.cartera(sesion, org.id)

    assert [c.id for c in cheques] == [con_fecha.id, sin_fecha.id]


def test_la_cartera_de_otra_org_no_se_ve(sesion, org):
    """RLS: desde la org vecina, esta cartera no existe."""
    _cobrar_con_cheque(sesion, org)

    eng = create_engine(APP_URL)
    conn = eng.connect()
    trans = conn.begin()
    with Session(bind=conn) as s:
        set_guc(s, ORG_GUC, str(org.vecina))
        assert service.cartera(s, org.vecina) == ([], 0)
        assert service.valor_en_cartera(s, org.vecina) == Decimal("0")
    trans.rollback()
    conn.close()
    eng.dispose()


# =========================================================================== HTTP (contrato)


@pytest.fixture
def cliente(org, monkeypatch):
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


@pytest.fixture
def cheque_http(cliente, org):
    """Un cheque COMMITEADO, para los tests de HTTP. Los de service corren sobre una transacción
    que hace rollback; estos no pueden, porque `get_tenant` commitea."""
    eng = create_engine(APP_URL)
    with Session(eng) as s:
        set_guc(s, ORG_GUC, str(org.id))
        asiento = service.asentar_documento(
            s,
            org.id,
            concepto="cobranza",
            ref_tipo="recibo",
            ref_id=int(datetime.now(UTC).timestamp() * 1000) % 1_000_000,
            formas=[("cheque", IMPORTE)],
        )
        cheque_id = asiento.cheques[0].id
        s.commit()
    eng.dispose()
    return cheque_id


def test_endpoint_cartera_shape(cliente, cheque_http):
    r = cliente.get("/caja/cheques")
    assert r.status_code == 200
    body = r.json()

    assert set(body) == {"items", "total", "valor_en_cartera"}
    # Plata como STRING, nunca float: la regla no negociable llegando al JSON.
    assert isinstance(body["valor_en_cartera"], str)
    assert isinstance(body["items"][0]["importe"], str)


def test_endpoint_cobrar_devuelve_el_papel_y_los_saldos(cliente, cheque_http):
    antes = Decimal(cliente.get("/caja/saldo").json()["efectivo"])

    r = cliente.post(f"/caja/cheques/{cheque_http}/cobrar")
    assert r.status_code == 200
    body = r.json()

    assert body["cheque"]["estado"] == "cobrado"
    assert Decimal(body["saldos"]["efectivo"]) == antes + IMPORTE
    assert {m["concepto"] for m in body["movimientos"]} == {
        "cheque_cobrado_cartera",
        "cheque_cobrado",
    }


def test_endpoint_transicion_invalida_es_422(cliente, cheque_http):
    cliente.post(f"/caja/cheques/{cheque_http}/cobrar")

    r = cliente.post(f"/caja/cheques/{cheque_http}/cobrar")

    assert r.status_code == 422


def test_endpoint_cheque_inexistente_es_404(cliente):
    """No 200 con un cuerpo vacío, y no 422: el recurso no existe."""
    r = cliente.post("/caja/cheques/999999/cobrar")

    assert r.status_code == 404


def test_endpoint_estado_inventado_es_422(cliente):
    """El filtro muere en Pydantic en vez de devolver una lista vacía sin explicar por qué."""
    r = cliente.get("/caja/cheques?estado=extraviado")

    assert r.status_code == 422


def test_endpoint_conciliar_exige_fecha(cliente, cheque_http):
    """Sin fecha no se puede auditar, que es todo el punto de conciliar."""
    # Primero pasa por el banco: un cheque en cartera todavía no se concilia.
    cliente.post(f"/caja/cheques/{cheque_http}/cobrar")

    assert cliente.post(f"/caja/cheques/{cheque_http}/conciliar", json={}).status_code == 422

    r = cliente.post(
        f"/caja/cheques/{cheque_http}/conciliar", json={"fecha": date.today().isoformat()}
    )
    assert r.status_code == 200
    assert r.json()["conciliado"] is True


def test_endpoint_conciliar_un_cheque_en_cartera_es_422(cliente, cheque_http):
    """La reja del estado también por HTTP, con un mensaje que explica el porqué."""
    r = cliente.post(
        f"/caja/cheques/{cheque_http}/conciliar", json={"fecha": date.today().isoformat()}
    )

    assert r.status_code == 422
    assert "banco" in r.json()["detail"]
