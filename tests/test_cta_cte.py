"""Cuenta corriente de clientes: listado de cuentas y extracto con saldo acumulado.

Contra Postgres real, como el resto de la suite: el saldo sale de una VISTA y el acumulado de una
window function, así que nada de esto se puede testear contra un doble.

Lo que no puede faltar: que el saldo acumulado NO dependa de la página pedida (el bug clásico de
calcular la ventana después del LIMIT, o peor, en el front), que dos movimientos del mismo día no
compartan acumulado (el frame RANGE por defecto), y que el LEFT JOIN no se coma a los clientes
que nunca operaron a cuenta corriente.

Dos estilos, como el repo:
- Patrón A (service directo como app_user, sujeto a RLS): la lógica de acumulado/filtro/orden.
- Patrón B (TestClient con JWT): el contrato HTTP, incluidos los endpoints de cobranza y saldo
  que existían desde el slice 1 y hasta hoy no tenían un solo test.
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

from app.clientes import service as clientes
from app.core import db as core_db
from app.core.config import get_settings
from app.core.db import ORG_GUC, set_guc
from app.core.models import Miembro, Organizacion
from app.main import app
from app.ventas import service
from app.ventas.models import CtaCteMovimiento
from tests.conftest import APP_URL, OWNER_URL

#: El ledger sembrado para CLI-DEUDA. Fechas explícitas: `registrar_cobranza` no acepta fecha,
#: así que los movimientos se insertan a mano para poder probar el orden cronológico.
#: (fecha, tipo, debe, haber) -> acumulado esperado
LEDGER = [
    ("2026-01-10", "venta", "1000", "0"),  # 1000
    ("2026-02-15", "cobranza", "0", "300"),  # 700
    ("2026-03-20", "venta", "500", "0"),  # 1200
    ("2026-03-20", "venta", "200", "0"),  # 1400  <- mismo día que el anterior, a propósito
    ("2026-04-05", "nota_credito", "0", "100"),  # 1300
]
ACUMULADOS_ASC = [Decimal(v) for v in ("1000", "700", "1200", "1400", "1300")]
SALDO_DEUDA = Decimal("1300")


@pytest.fixture(scope="module")
def org(migrated_db):
    """Org con tres clientes: uno con ledger, uno sin movimientos, uno con saldo a favor.

    Más una org vecina con deuda, que ningún query de esta org debe ver.
    """
    org_id, user_id, vecina_id = uuid4(), uuid4(), uuid4()
    eng = create_engine(OWNER_URL)
    with Session(eng) as s:
        s.add(Organizacion(id=org_id, nombre="Org CtaCte"))
        s.add(Organizacion(id=vecina_id, nombre="Org Vecina"))
        s.flush()

        deuda = clientes.crear_cliente(
            s, org_id, codigo="CLI-DEUDA", denominacion="Ferretería Alsina"
        )
        clientes.crear_cliente(s, org_id, codigo="CLI-CERO", denominacion="Taller Belgrano")
        favor = clientes.crear_cliente(s, org_id, codigo="CLI-FAVOR", denominacion="Zubiría SRL")

        for fecha, tipo, debe, haber in LEDGER:
            s.add(
                CtaCteMovimiento(
                    org_id=org_id,
                    cliente_id=deuda.id,
                    fecha=date.fromisoformat(fecha),
                    tipo=tipo,
                    debe=Decimal(debe),
                    haber=Decimal(haber),
                )
            )
        # Saldo a favor: cobró de más o le quedó una NC sin usar.
        s.add(
            CtaCteMovimiento(
                org_id=org_id,
                cliente_id=favor.id,
                fecha=date(2026, 5, 1),
                tipo="cobranza",
                haber=Decimal("500"),
            )
        )

        ajeno = clientes.crear_cliente(s, vecina_id, codigo="CLI-X", denominacion="No Se Ve SA")
        s.add(
            CtaCteMovimiento(
                org_id=vecina_id,
                cliente_id=ajeno.id,
                fecha=date(2026, 1, 1),
                tipo="venta",
                debe=Decimal("99999"),
            )
        )

        s.add(Miembro(org_id=org_id, user_id=user_id, rol="admin"))  # sin esto get_tenant da 403
        s.commit()
        ids = SimpleNamespace(deuda=deuda.id, favor=favor.id)
    eng.dispose()
    return SimpleNamespace(id=org_id, user=user_id, vecina=vecina_id, cli=ids)


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


# =========================================================================== saldo acumulado


def test_saldo_acumulado_es_cronologico(sesion, org):
    """Las filas vuelven DESC (más reciente arriba) pero el acumulado se suma ASC."""
    filas, _ = service.movimientos_cliente(sesion, org.id, org.cli.deuda)
    assert [f.saldo_acumulado for f in filas] == list(reversed(ACUMULADOS_ASC))


def test_saldo_acumulado_no_depende_de_la_pagina(sesion, org):
    """EL test. Si la window se calculara después del LIMIT —o en el front— la página 2
    arrancaría el acumulado de cero y esto explotaría."""
    completo, _ = service.movimientos_cliente(sesion, org.id, org.cli.deuda, limite=100)
    pagina, _ = service.movimientos_cliente(sesion, org.id, org.cli.deuda, limite=2, offset=2)

    assert [f.saldo_acumulado for f in pagina] == [f.saldo_acumulado for f in completo[2:4]]
    assert [f.id for f in pagina] == [f.id for f in completo[2:4]]


def test_movimientos_del_mismo_dia_no_comparten_acumulado(sesion, org):
    """Frame RANGE por defecto = todos los peers de la misma fecha cierran con el mismo saldo.
    En un mostrador dos ventas el mismo día es lo NORMAL, así que esto tiene que estar blindado.
    """
    filas, _ = service.movimientos_cliente(sesion, org.id, org.cli.deuda)
    del_20 = [f.saldo_acumulado for f in filas if f.fecha == date(2026, 3, 20)]

    assert len(del_20) == 2
    assert len(set(del_20)) == 2, "dos movimientos del mismo día comparten acumulado"
    assert sorted(del_20) == [Decimal("1200"), Decimal("1400")]


def test_acumulado_del_mas_reciente_iguala_la_vista(sesion, org):
    """Ata la window function a la VISTA `cliente_saldo`. Si divergen, una de las dos miente."""
    filas, _ = service.movimientos_cliente(sesion, org.id, org.cli.deuda)
    assert filas[0].saldo_acumulado == service.saldo_cliente(sesion, org.id, org.cli.deuda)
    assert filas[0].saldo_acumulado == SALDO_DEUDA


def test_paginacion_no_repite_ni_saltea(sesion, org):
    p1, total = service.movimientos_cliente(sesion, org.id, org.cli.deuda, limite=3, offset=0)
    p2, _ = service.movimientos_cliente(sesion, org.id, org.cli.deuda, limite=3, offset=3)

    ids1, ids2 = {f.id for f in p1}, {f.id for f in p2}
    assert total == len(LEDGER)
    assert not ids1 & ids2
    assert len(ids1 | ids2) == total


def test_extracto_de_cliente_sin_movimientos_es_vacio(sesion, org):
    cero = clientes.obtener_cliente(sesion, org.id, "CLI-CERO")
    filas, total = service.movimientos_cliente(sesion, org.id, cero.id)
    assert (filas, total) == ([], 0)


# =========================================================================== listado de cuentas


def test_filtra_saldo_cero_por_defecto(sesion, org):
    cuentas, total, _ = service.listar_cuentas_clientes(sesion, org.id)
    codigos = [c.codigo for c in cuentas]

    assert "CLI-CERO" not in codigos
    assert set(codigos) == {"CLI-DEUDA", "CLI-FAVOR"}
    assert total == 2


def test_incluye_cuenta_sin_movimientos_con_saldo_cero(sesion, org):
    """Valida el LEFT JOIN: `cliente_saldo` no tiene fila para quien nunca operó a cuenta.
    Con un INNER JOIN, CLI-CERO simplemente no existiría."""
    cuentas, total, _ = service.listar_cuentas_clientes(sesion, org.id, solo_con_saldo=False)
    por_codigo = {c.codigo: c for c in cuentas}

    assert total == 3
    assert por_codigo["CLI-CERO"].saldo == Decimal("0")


def test_ordena_por_mayor_deuda_primero(sesion, org):
    cuentas, _, _ = service.listar_cuentas_clientes(sesion, org.id, solo_con_saldo=False)
    assert [c.codigo for c in cuentas] == ["CLI-DEUDA", "CLI-CERO", "CLI-FAVOR"]


def test_saldo_a_favor_entra_al_listado(sesion, org):
    """Un saldo negativo NO es saldo cero: el filtro `!= 0` lo tiene que dejar pasar."""
    cuentas, _, _ = service.listar_cuentas_clientes(sesion, org.id)
    favor = next(c for c in cuentas if c.codigo == "CLI-FAVOR")
    assert favor.saldo == Decimal("-500")


def test_saldo_total_suma_el_conjunto_filtrado_no_la_pagina(sesion, org):
    """Con una sola fila en la página, el total sigue siendo el de las dos cuentas con saldo.
    Y mezcla signos: 1300 - 500 = 800. Es el NETO a cobrar, no el total adeudado."""
    cuentas, total, saldo_total = service.listar_cuentas_clientes(sesion, org.id, limite=1)

    assert len(cuentas) == 1
    assert total == 2
    assert saldo_total == Decimal("800")


def test_total_aplica_los_mismos_filtros_que_la_pagina(sesion, org):
    cuentas, total, saldo_total = service.listar_cuentas_clientes(sesion, org.id, buscar="alsina")

    assert [c.codigo for c in cuentas] == ["CLI-DEUDA"]
    assert total == 1
    assert saldo_total == SALDO_DEUDA


def test_busca_por_codigo_ademas_de_nombre(sesion, org):
    cuentas, _, _ = service.listar_cuentas_clientes(sesion, org.id, buscar="CLI-FAVOR")
    assert [c.codigo for c in cuentas] == ["CLI-FAVOR"]


def test_expone_el_limite_de_cuenta_corriente(sesion, org):
    """Informativo: hoy NADIE lo hace cumplir. Se muestra para que el mostrador lo vea."""
    cuentas, _, _ = service.listar_cuentas_clientes(sesion, org.id)
    assert all(c.limite is not None for c in cuentas)


def test_cuentas_no_cruza_orgs(sesion, org):
    """La org vecina tiene un cliente con 99999 de deuda. Acá no se ve, ni en el saldo_total."""
    cuentas, total, saldo_total = service.listar_cuentas_clientes(sesion, org.id)

    assert "CLI-X" not in [c.codigo for c in cuentas]
    assert total == 2
    assert saldo_total == Decimal("800")


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


def test_endpoint_cuenta_corriente_shape(cliente):
    r = cliente.get("/ventas/cuenta-corriente?limite=1")
    assert r.status_code == 200
    body = r.json()

    assert set(body) == {"items", "total", "saldo_total"}
    assert len(body["items"]) == 1
    assert body["total"] == 2  # el total es del conjunto filtrado, no de la página
    assert set(body["items"][0]) == {"id", "codigo", "nombre", "saldo", "limite"}


def test_endpoint_cuenta_corriente_no_lo_captura_la_ruta_de_detalle(cliente):
    """`/ventas/cuenta-corriente` es un solo segmento: si quedara declarada después de
    `/ventas/{venta_id}`, el conversor int devolvería 422 en vez de listar."""
    assert cliente.get("/ventas/cuenta-corriente").status_code == 200


def test_endpoint_movimientos_shape(cliente, org):
    r = cliente.get(f"/ventas/clientes/{org.cli.deuda}/movimientos")
    assert r.status_code == 200
    body = r.json()

    assert set(body) == {"items", "total", "cuenta"}
    assert body["total"] == len(LEDGER)
    assert body["cuenta"]["codigo"] == "CLI-DEUDA"
    assert body["cuenta"]["saldo"] == "1300.00"


def test_plata_viaja_como_string(cliente, org):
    """Fija el contrato del que dependen todos los `z.string()` del front. Si algún día un
    Decimal saliera como number, los schemas Zod romperían en runtime y esto avisa antes."""
    r = cliente.get(f"/ventas/clientes/{org.cli.deuda}/movimientos")
    mov = r.json()["items"][0]

    for campo in ("debe", "haber", "saldo_acumulado"):
        assert isinstance(mov[campo], str), f"{campo} salió como {type(mov[campo])}"

    listado = cliente.get("/ventas/cuenta-corriente").json()
    assert isinstance(listado["saldo_total"], str)
    assert isinstance(listado["items"][0]["saldo"], str)


def test_endpoint_movimientos_de_cliente_inexistente_404(cliente):
    assert cliente.get("/ventas/clientes/999999/movimientos").status_code == 404


def test_endpoint_cobranza_registra_y_devuelve_saldo(cliente, org):
    """El POST existía desde el slice 1 y no tenía un solo test HTTP.

    Este SÍ commitea (lo hace `get_tenant`), así que no asume el saldo inicial: lo lee antes.
    """
    antes = Decimal(
        cliente.get(f"/ventas/clientes/{org.cli.deuda}/movimientos").json()["cuenta"]["saldo"]
    )

    r = cliente.post("/ventas/cobranzas", json={"cliente_codigo": "CLI-DEUDA", "monto": "300.00"})
    assert r.status_code == 201
    body = r.json()

    assert Decimal(body["saldo"]) == antes - Decimal("300")
    assert body["movimiento_id"] > 0


def test_endpoint_cobranza_monto_cero_es_422(cliente):
    r = cliente.post("/ventas/cobranzas", json={"cliente_codigo": "CLI-DEUDA", "monto": "0"})
    assert r.status_code == 422
