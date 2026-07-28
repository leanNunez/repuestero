"""Caja: carga manual, saldo por forma y extracto con acumulado.

Dos patrones, como el resto de la suite:
- Patrón A (service contra Postgres con `app_user`): la aritmética del libro.
- Patrón B (TestClient con JWT): el contrato HTTP, incluida la reja de los conceptos derivados.

Lo que no puede faltar:
- Que el acumulado NO dependa de la página pedida (el bug clásico de los extractos).
- Que el acumulado sea POR FORMA: mezclar el cajón con lo que entró por transferencia daría un
  número que no se corresponde con nada que se pueda contar.
- Que un concepto derivado NO se pueda cargar a mano. Es el invariante del módulo.
- Que el signo lo ponga el concepto, no el que llama.
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
from app.core import db as core_db
from app.core.config import get_settings
from app.core.db import ORG_GUC, set_guc
from app.core.models import Miembro, Organizacion
from app.main import app
from tests.conftest import APP_URL, OWNER_URL

#: Movimientos sembrados en EFECTIVO, en orden cronológico. Los acumulados de abajo salen de acá.
LIBRO_EFECTIVO = (
    (date(2026, 3, 10), "aporte", "10000", "0"),
    (date(2026, 3, 12), "gasto", "0", "1500"),
    (date(2026, 3, 15), "retiro", "0", "2500"),
    (date(2026, 3, 20), "aporte", "5000", "0"),
)
#: 10000 -> 8500 -> 6000 -> 11000. Escritos a mano a propósito: si el service se rompe, un
#: acumulado calculado en el test se rompería igual y el test pasaría igual.
ACUMULADOS_ASC = (Decimal("10000"), Decimal("8500"), Decimal("6000"), Decimal("11000"))
SALDO_EFECTIVO = Decimal("11000")


@pytest.fixture(scope="module")
def org(migrated_db):
    """Org con un libro de caja sembrado en efectivo y un movimiento en transferencia.

    El de transferencia existe para probar que las particiones NO se mezclan: si el acumulado
    fuera global, sus 20.000 se colarían en el saldo del cajón.
    """
    org_id, vecina_id, user_id = uuid4(), uuid4(), uuid4()
    eng = create_engine(OWNER_URL)
    with Session(eng) as s:
        s.add(Organizacion(id=org_id, nombre="Org Caja Service"))
        s.add(Organizacion(id=vecina_id, nombre="Org Vecina Caja Service"))
        s.flush()
        set_guc(s, ORG_GUC, str(org_id))

        for fecha, concepto, ingreso, egreso in LIBRO_EFECTIVO:
            service.registrar_movimiento(
                s,
                org_id,
                concepto=concepto,
                forma="efectivo",
                monto=Decimal(ingreso) if ingreso != "0" else Decimal(egreso),
                fecha=fecha,
            )
        service.registrar_movimiento(
            s,
            org_id,
            concepto="aporte",
            forma="transferencia",
            monto=Decimal("20000"),
            fecha=date(2026, 3, 11),
        )

        s.add(Miembro(org_id=org_id, user_id=user_id, rol="admin"))  # sin esto get_tenant da 403
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


# =========================================================================== caja en negativo


def test_un_saldo_negativo_advierte(sesion, org):
    """Un saldo negativo es físicamente imposible: nadie sacó plata que no estaba. O se cargó de
    más, o falta cargar un ingreso. El sistema lo dice con el número, no con un "revisá la caja"."""
    service.registrar_movimiento(
        sesion, org.id, concepto="gasto", forma="efectivo", monto=SALDO_EFECTIVO + Decimal("500")
    )

    avisos = service.advertencias_de_saldo(sesion, org.id, formas=["efectivo"])

    assert len(avisos) == 1
    assert "-500.00" in avisos[0]
    assert "efectivo" in avisos[0].lower()


def test_advertir_NO_bloquea_el_movimiento(sesion, org):
    """El contrato de la regla. Sin roles ni override, frenar el gasto deja el mostrador parado y la
    operación termina ocurriendo fuera del sistema, que es peor que un cajón en rojo."""
    m = service.registrar_movimiento(
        sesion, org.id, concepto="gasto", forma="efectivo", monto=SALDO_EFECTIVO + Decimal("500")
    )

    assert m.id is not None, "el movimiento se escribe igual"
    assert service.saldo_efectivo(sesion, org.id) == Decimal("-500")


def test_un_saldo_sano_no_advierte_nada(sesion, org):
    """La otra mitad: si advirtiera siempre, nadie leería la advertencia cuando importa."""
    service.registrar_movimiento(
        sesion, org.id, concepto="gasto", forma="efectivo", monto=Decimal("100")
    )

    assert service.advertencias_de_saldo(sesion, org.id) == []


def test_solo_advierte_de_las_formas_que_se_tocaron(sesion, org):
    """Un negativo viejo en otra forma no tiene nada que ver con lo que la persona acaba de hacer.
    Mezclarlos haría que el aviso se lea como ruido."""
    service.registrar_movimiento(
        sesion, org.id, concepto="gasto", forma="tarjeta", monto=Decimal("300")
    )

    assert service.advertencias_de_saldo(sesion, org.id, formas=["efectivo"]) == []
    assert len(service.advertencias_de_saldo(sesion, org.id, formas=["tarjeta"])) == 1
    # Sin argumento revisa TODAS: es lo que sirve para una pantalla.
    assert len(service.advertencias_de_saldo(sesion, org.id)) == 1


def test_advierte_de_cada_forma_en_negativo(sesion, org):
    for forma in ("efectivo", "tarjeta"):
        service.registrar_movimiento(
            sesion, org.id, concepto="gasto", forma=forma, monto=SALDO_EFECTIVO + Decimal("1")
        )

    avisos = service.advertencias_de_saldo(sesion, org.id)

    assert len(avisos) == 2


# =========================================================================== el signo


def test_el_concepto_determina_el_signo(sesion, org):
    """No se pide "ingreso o egreso": lo dice el concepto. Pedirlo dos veces es pedir que la
    segunda se contradiga."""
    aporte = service.registrar_movimiento(
        sesion, org.id, concepto="aporte", forma="efectivo", monto=Decimal("100")
    )
    gasto = service.registrar_movimiento(
        sesion, org.id, concepto="gasto", forma="efectivo", monto=Decimal("40")
    )

    assert (aporte.ingreso, aporte.egreso) == (Decimal("100"), Decimal("0"))
    assert (gasto.ingreso, gasto.egreso) == (Decimal("0"), Decimal("40"))


def test_un_monto_cero_o_negativo_es_invalido(sesion, org):
    for monto in (Decimal("0"), Decimal("-5")):
        with pytest.raises(service.CajaInvalida, match="mayor a cero"):
            service.registrar_movimiento(
                sesion, org.id, concepto="gasto", forma="efectivo", monto=monto
            )


def test_un_movimiento_manual_no_lleva_referencia(sesion, org):
    """Manual = sin documento detrás. Es lo que lo distingue de un derivado en el extracto."""
    m = service.registrar_movimiento(
        sesion, org.id, concepto="gasto", forma="efectivo", monto=Decimal("10")
    )

    assert m.ref_tipo is None
    assert m.ref_id is None


# =========================================================================== la reja del invariante


@pytest.mark.parametrize(
    "concepto", ["cobranza", "pago_proveedor", "cheque_cobrado", "cheque_rechazado"]
)
def test_un_concepto_derivado_no_se_carga_a_mano(sesion, org, concepto):
    """EL invariante del módulo: si hay documento, caja no se toca a mano.

    Sin esta reja alguien podría cargar "cobranza $5.000" a mano ADEMÁS del recibo que ya la
    generó, y la caja diría el doble de lo que hay en el cajón. Es el desastre que este módulo
    existe para no repetir, y por eso se testean los cuatro conceptos y no uno de muestra.
    """
    with pytest.raises(service.CajaInvalida, match="lo emite el sistema"):
        service.registrar_movimiento(
            sesion, org.id, concepto=concepto, forma="efectivo", monto=Decimal("5000")
        )


def test_un_concepto_inventado_es_invalido(sesion, org):
    with pytest.raises(service.CajaInvalida, match="No existe el concepto"):
        service.registrar_movimiento(
            sesion, org.id, concepto="propina", forma="efectivo", monto=Decimal("100")
        )


# =========================================================================== saldo


def test_el_saldo_se_discrimina_por_forma(sesion, org):
    saldos = service.saldo_por_forma(sesion, org.id)

    assert saldos["efectivo"] == SALDO_EFECTIVO
    assert saldos["transferencia"] == Decimal("20000")


def test_una_forma_sin_movimientos_vale_cero_y_no_falta(sesion, org):
    """La vista no trae fila para una forma sin movimientos. Que la ausencia sea el cero se
    resuelve UNA vez, en el service, y no en cada caller con un `.get(forma, 0)`."""
    saldos = service.saldo_por_forma(sesion, org.id)

    assert saldos["tarjeta"] == Decimal("0")
    assert set(saldos) == {"efectivo", "cheque", "transferencia", "tarjeta"}


def test_saldo_efectivo_es_el_del_cajon(sesion, org):
    """No mezcla con transferencia: es LA pregunta de caja y tiene que tener UNA respuesta."""
    assert service.saldo_efectivo(sesion, org.id) == SALDO_EFECTIVO


# =========================================================================== extracto


def test_el_acumulado_es_cronologico(sesion, org):
    """El extracto sale al revés (más reciente primero), así que los acumulados también."""
    filas, _ = service.movimientos(sesion, org.id, forma="efectivo")

    assert [f.saldo_acumulado for f in filas] == list(reversed(ACUMULADOS_ASC))


def test_el_acumulado_no_depende_de_la_pagina(sesion, org):
    """EL bug clásico de los extractos: calcular el acumulado sobre la ventana ya recortada hace
    que la página 2 arranque de cero. Por eso la window va en una subquery, antes del LIMIT."""
    completo, _ = service.movimientos(sesion, org.id, forma="efectivo", limite=100)
    pagina, _ = service.movimientos(sesion, org.id, forma="efectivo", limite=2, offset=1)

    assert [f.saldo_acumulado for f in pagina] == [f.saldo_acumulado for f in completo[1:3]]


def test_el_acumulado_cierra_contra_la_vista(sesion, org):
    """Ata la window function a la VISTA `caja_saldo`. Si divergen, una de las dos miente."""
    filas, _ = service.movimientos(sesion, org.id, forma="efectivo")

    assert filas[0].saldo_acumulado == service.saldo_efectivo(sesion, org.id)


def test_el_acumulado_no_mezcla_formas(sesion, org):
    """La razón de que la window particione por forma.

    Si fuera global, los 20.000 de la transferencia del 11-mar se sumarían al acumulado del cajón
    y el extracto diría que hay plata que nadie puede contar.
    """
    filas, _ = service.movimientos(sesion, org.id, forma="efectivo")
    assert max(f.saldo_acumulado for f in filas) == SALDO_EFECTIVO

    transferencia, _ = service.movimientos(sesion, org.id, forma="transferencia")
    assert [f.saldo_acumulado for f in transferencia] == [Decimal("20000")]


def test_sin_filtro_trae_todas_las_formas(sesion, org):
    filas, total = service.movimientos(sesion, org.id)

    assert total == len(LIBRO_EFECTIVO) + 1
    assert {f.forma for f in filas} == {"efectivo", "transferencia"}


# =========================================================================== aislamiento


def test_la_caja_de_otra_org_no_se_ve(sesion, org):
    """RLS: desde la org vecina, este libro no existe."""
    eng = create_engine(APP_URL)
    conn = eng.connect()
    trans = conn.begin()
    with Session(bind=conn) as s:
        set_guc(s, ORG_GUC, str(org.vecina))
        filas, total = service.movimientos(s, org.vecina)
        assert (filas, total) == ([], 0)
        assert service.saldo_efectivo(s, org.vecina) == Decimal("0")
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


def test_endpoint_saldo_shape(cliente):
    r = cliente.get("/caja/saldo")
    assert r.status_code == 200
    body = r.json()

    # `cheques_en_cartera` va aparte de `por_forma["cheque"]` y NO es redundante: aquel es el neto
    # de recibidos menos emitidos y puede ser negativo; este es lo que hay en la mano.
    assert set(body) == {"efectivo", "por_forma", "cheques_en_cartera"}
    assert set(body["por_forma"]) == {"efectivo", "cheque", "transferencia", "tarjeta"}
    # Plata como STRING, nunca float: es la regla no negociable del proyecto llegando al JSON.
    assert isinstance(body["efectivo"], str)
    assert isinstance(body["cheques_en_cartera"], str)


def test_endpoint_movimientos_shape(cliente):
    r = cliente.get("/caja/movimientos?forma=efectivo&limite=1")
    assert r.status_code == 200
    body = r.json()

    assert set(body) == {"items", "total"}
    # NO se afirma el total exacto: `test_endpoint_registra_un_gasto…` COMMITEA, así que el conteo
    # depende del orden de ejecución. Este test es de forma; el conteo lo cubren los de service,
    # que corren sobre una transacción que hace rollback.
    assert body["total"] >= len(LIBRO_EFECTIVO)

    mov = body["items"][0]
    for campo in ("ingreso", "egreso", "saldo_acumulado"):
        assert isinstance(mov[campo], str), f"{campo} salió como {type(mov[campo])}"


def test_endpoint_registra_un_gasto_y_devuelve_el_saldo(cliente):
    """Este SÍ commitea (lo hace `get_tenant`), así que no asume el saldo inicial: lo lee antes."""
    antes = Decimal(cliente.get("/caja/saldo").json()["efectivo"])

    r = cliente.post(
        "/caja/movimientos",
        json={"concepto": "gasto", "forma": "efectivo", "monto": "750.00", "detalle": "flete"},
    )
    assert r.status_code == 201
    body = r.json()

    assert Decimal(body["saldo"]) == antes - Decimal("750")
    assert body["movimiento_id"] > 0


def test_endpoint_advierte_del_negativo_pero_devuelve_201(cliente):
    """El contrato completo por HTTP: la operación se ACEPTA (201) y el aviso viaja en el cuerpo.

    Si esto fuera un 422, el mostrador quedaría trabado esperando a alguien que autorice, y no hay
    quién: no existen roles todavía.
    """
    saldo = Decimal(cliente.get("/caja/saldo").json()["efectivo"])

    r = cliente.post(
        "/caja/movimientos",
        json={"concepto": "retiro", "forma": "efectivo", "monto": str(saldo + Decimal("1000"))},
    )

    assert r.status_code == 201
    body = r.json()
    assert len(body["advertencias"]) == 1
    assert Decimal(body["saldo"]) == Decimal("-1000")

    # Se deja la caja como estaba: este test COMMITEA (lo hace `get_tenant`) y los demás leen de acá.
    cliente.post(
        "/caja/movimientos",
        json={"concepto": "aporte", "forma": "efectivo", "monto": str(saldo + Decimal("1000"))},
    )


def test_endpoint_no_advierte_cuando_el_saldo_queda_sano(cliente):
    r = cliente.post(
        "/caja/movimientos", json={"concepto": "gasto", "forma": "efectivo", "monto": "1"}
    )

    assert r.status_code == 201
    assert r.json()["advertencias"] == []


def test_endpoint_rechaza_un_concepto_derivado(cliente):
    """La reja del invariante en el borde HTTP: muere en Pydantic, sin llegar al service."""
    r = cliente.post(
        "/caja/movimientos", json={"concepto": "cobranza", "forma": "efectivo", "monto": "5000"}
    )
    assert r.status_code == 422


def test_endpoint_rechaza_monto_cero(cliente):
    r = cliente.post(
        "/caja/movimientos", json={"concepto": "gasto", "forma": "efectivo", "monto": "0"}
    )
    assert r.status_code == 422


def test_endpoint_rechaza_una_fecha_futura(cliente):
    """La ventana de fechas es política de la API, compartida con los dos ledgers de cta cte."""
    manana = (date.today() + timedelta(days=1)).isoformat()
    r = cliente.post(
        "/caja/movimientos",
        json={"concepto": "gasto", "forma": "efectivo", "monto": "10", "fecha": manana},
    )
    assert r.status_code == 422
