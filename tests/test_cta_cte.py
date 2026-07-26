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
from sqlalchemy import create_engine, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.asistente import grafo, llm
from app.asistente import service as asistente_service
from app.asistente.esquema import ESQUEMA
from app.clientes import service as clientes
from app.compras import service as compras
from app.compras.models import ProvCtaCteMovimiento
from app.compras.schemas import CuentaLeer as CuentaProveedorLeer
from app.core import db as core_db
from app.core.config import get_settings
from app.core.db import ORG_GUC, set_guc
from app.core.fechas import DIAS_RETROACTIVIDAD, hoy
from app.core.models import Miembro, Organizacion
from app.main import app
from app.proveedores import service as proveedores
from app.ventas import service
from app.ventas.models import CtaCteMovimiento
from tests.conftest import APP_URL, OWNER_URL

#: El ledger sembrado para CLI-DEUDA. Se inserta a mano para fijar fechas de 2026 estables: los
#: acumulados esperados de abajo dependen del orden cronológico exacto, y el reloj de hoy los movería
#: cada vez que corre la suite.
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

#: Ledger de PROV-DEUDA. Mismo criterio: dos movimientos el 2026-03-25 a propósito.
LEDGER_PROV = [
    ("2026-01-12", "compra", "2000", "0"),  # 2000
    ("2026-02-20", "pago", "0", "500"),  # 1500
    ("2026-03-25", "compra", "300", "0"),  # 1800
    ("2026-03-25", "compra", "700", "0"),  # 2500
]
ACUMULADOS_PROV_ASC = [Decimal(v) for v in ("2000", "1500", "1800", "2500")]
SALDO_PROV = Decimal("2500")


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

        prov = proveedores.crear_proveedor(
            s, org_id, codigo="PROV-DEUDA", razon_social="Bosch Argentina"
        )
        proveedores.crear_proveedor(
            s, org_id, codigo="PROV-CERO", razon_social="Distribuidora Norte"
        )
        prov_favor = proveedores.crear_proveedor(
            s, org_id, codigo="PROV-FAVOR", razon_social="Repuestos Sur"
        )

        for fecha, tipo, debe, haber in LEDGER_PROV:
            s.add(
                ProvCtaCteMovimiento(
                    org_id=org_id,
                    proveedor_id=prov.id,
                    fecha=date.fromisoformat(fecha),
                    tipo=tipo,
                    debe=Decimal(debe),
                    haber=Decimal(haber),
                )
            )
        # Le pagamos de más: saldo a favor nuestro.
        s.add(
            ProvCtaCteMovimiento(
                org_id=org_id,
                proveedor_id=prov_favor.id,
                fecha=date(2026, 5, 2),
                tipo="pago",
                haber=Decimal("200"),
            )
        )

        s.add(Miembro(org_id=org_id, user_id=user_id, rol="admin"))  # sin esto get_tenant da 403
        s.commit()
        ids = SimpleNamespace(deuda=deuda.id, favor=favor.id)
        prov_ids = SimpleNamespace(deuda=prov.id, favor=prov_favor.id)
    eng.dispose()
    return SimpleNamespace(id=org_id, user=user_id, vecina=vecina_id, cli=ids, prov=prov_ids)


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


def _cobrar(sesion, org_id, *, cliente_codigo: str, monto: Decimal, **kw) -> CtaCteMovimiento:
    """Cobra en efectivo y devuelve el MOVIMIENTO.

    `registrar_cobranza` emite un recibo y devuelve los dos (`Cobranza`), pero acá el sujeto es
    siempre el ledger: el acumulado, el orden, el saldo. El detalle de formas de pago y el recibo
    en sí se testean en `tests/test_recibos.py`.
    """
    return service.registrar_cobranza(
        sesion,
        org_id,
        cliente_codigo=cliente_codigo,
        monto=monto,
        formas_pago=[service.FormaPago("efectivo", monto)],
        **kw,
    ).movimiento


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


# =========================================================================== proveedores
# Espejo explícito de los de arriba, sin parametrizar: las fixtures difieren y en tests la
# claridad gana. Son la otra mitad del circuito — sin esto, compras registra deuda que nadie ve.


def test_prov_saldo_acumulado_es_cronologico(sesion, org):
    filas, _ = compras.movimientos_proveedor(sesion, org.id, org.prov.deuda)
    assert [f.saldo_acumulado for f in filas] == list(reversed(ACUMULADOS_PROV_ASC))


def test_prov_saldo_acumulado_no_depende_de_la_pagina(sesion, org):
    completo, _ = compras.movimientos_proveedor(sesion, org.id, org.prov.deuda, limite=100)
    pagina, _ = compras.movimientos_proveedor(sesion, org.id, org.prov.deuda, limite=2, offset=1)

    assert [f.saldo_acumulado for f in pagina] == [f.saldo_acumulado for f in completo[1:3]]


def test_prov_movimientos_del_mismo_dia_no_comparten_acumulado(sesion, org):
    filas, _ = compras.movimientos_proveedor(sesion, org.id, org.prov.deuda)
    del_25 = [f.saldo_acumulado for f in filas if f.fecha == date(2026, 3, 25)]

    assert sorted(del_25) == [Decimal("1800"), Decimal("2500")]


def test_prov_acumulado_del_mas_reciente_iguala_la_vista(sesion, org):
    filas, _ = compras.movimientos_proveedor(sesion, org.id, org.prov.deuda)
    assert filas[0].saldo_acumulado == compras.saldo_proveedor(sesion, org.id, org.prov.deuda)
    assert filas[0].saldo_acumulado == SALDO_PROV


def test_prov_filtra_saldo_cero_por_defecto(sesion, org):
    cuentas, total, saldo_total = compras.listar_cuentas_proveedores(sesion, org.id)

    assert set(c.codigo for c in cuentas) == {"PROV-DEUDA", "PROV-FAVOR"}
    assert total == 2
    assert saldo_total == Decimal("2300")  # 2500 - 200: neto a pagar, mezcla signos


def test_prov_incluye_cuenta_sin_movimientos_con_saldo_cero(sesion, org):
    """Valida el LEFT JOIN: a un proveedor al que siempre se le pagó al contado no le
    corresponde ninguna fila en `proveedor_saldo`."""
    cuentas, total, _ = compras.listar_cuentas_proveedores(sesion, org.id, solo_con_saldo=False)
    por_codigo = {c.codigo: c for c in cuentas}

    assert total == 3
    assert por_codigo["PROV-CERO"].saldo == Decimal("0")


def test_prov_ordena_por_mayor_deuda_primero(sesion, org):
    cuentas, _, _ = compras.listar_cuentas_proveedores(sesion, org.id, solo_con_saldo=False)
    assert [c.codigo for c in cuentas] == ["PROV-DEUDA", "PROV-CERO", "PROV-FAVOR"]


def test_prov_busca_por_razon_social(sesion, org):
    cuentas, total, _ = compras.listar_cuentas_proveedores(sesion, org.id, buscar="bosch")

    assert [c.codigo for c in cuentas] == ["PROV-DEUDA"]
    assert total == 1


def test_prov_limite_siempre_es_none(sesion, org):
    """Los proveedores no tienen límite de crédito. El campo existe solo para que el front
    tenga UN schema para las dos solapas, y el default del schema lo tiene que llenar.

    Se arma el `CuentaLeer` de verdad —no se mira la Row— porque lo que se está protegiendo es
    que la query pueda no traer la columna sin romper la serialización.
    """
    cuentas, _, _ = compras.listar_cuentas_proveedores(sesion, org.id)
    leidas = [CuentaProveedorLeer(**c._asdict()) for c in cuentas]

    assert leidas and all(c.limite is None for c in leidas)


# ==================================================================== ajustes de proveedor
# Espejo de la sección de clientes. Lo que cambia es el signo del significado, no la mecánica.


def _primer_movimiento_prov(sesion, org_id, proveedor_id, tipo) -> ProvCtaCteMovimiento:
    mov = sesion.scalars(
        select(ProvCtaCteMovimiento)
        .where(
            ProvCtaCteMovimiento.org_id == org_id,
            ProvCtaCteMovimiento.proveedor_id == proveedor_id,
            ProvCtaCteMovimiento.tipo == tipo,
        )
        .order_by(ProvCtaCteMovimiento.id)
    ).first()
    assert mov is not None, f"el fixture tiene que sembrar un movimiento {tipo!r}"
    return mov


def test_prov_storno_deja_el_saldo_igual_que_antes_del_pago(sesion, org):
    """El test que importa, del lado proveedor: la reversa cierra exacto contra la vista."""
    antes = compras.saldo_proveedor(sesion, org.id, org.prov.deuda)

    pago = compras.registrar_pago(
        sesion, org.id, proveedor_codigo="PROV-DEUDA", monto=Decimal("3000")
    )
    assert compras.saldo_proveedor(sesion, org.id, org.prov.deuda) == antes - Decimal("3000")

    compras.registrar_ajuste(
        sesion,
        org.id,
        proveedor_id=org.prov.deuda,
        motivo="pago cargado dos veces",
        revierte_movimiento_id=pago.id,
    )
    assert compras.saldo_proveedor(sesion, org.id, org.prov.deuda) == antes


def test_prov_storno_espeja_el_monto_y_referencia_el_original(sesion, org):
    pago = _primer_movimiento_prov(sesion, org.id, org.prov.deuda, "pago")

    ajuste = compras.registrar_ajuste(
        sesion,
        org.id,
        proveedor_id=org.prov.deuda,
        motivo="duplicado",
        revierte_movimiento_id=pago.id,
    )

    assert ajuste.tipo == "ajuste"
    assert (ajuste.debe, ajuste.haber) == (pago.haber, pago.debe)
    assert (ajuste.ref_tipo, ajuste.ref_id) == (compras.REF_REVERSA, pago.id)
    assert ajuste.motivo == "duplicado"


def test_prov_no_se_puede_revertir_dos_veces(sesion, org):
    pago = _primer_movimiento_prov(sesion, org.id, org.prov.deuda, "pago")
    compras.registrar_ajuste(
        sesion,
        org.id,
        proveedor_id=org.prov.deuda,
        motivo="primera",
        revierte_movimiento_id=pago.id,
    )

    with pytest.raises(compras.CompraInvalida, match="ya fue revertido"):
        compras.registrar_ajuste(
            sesion,
            org.id,
            proveedor_id=org.prov.deuda,
            motivo="segunda",
            revierte_movimiento_id=pago.id,
        )


def test_prov_el_indice_unico_ataja_la_doble_reversa_simultanea(sesion, org):
    """La garantía real es el índice de la 0009, no el chequeo del service."""
    pago = _primer_movimiento_prov(sesion, org.id, org.prov.deuda, "pago")
    compras.registrar_ajuste(
        sesion,
        org.id,
        proveedor_id=org.prov.deuda,
        motivo="primera",
        revierte_movimiento_id=pago.id,
    )

    sesion.add(
        ProvCtaCteMovimiento(
            org_id=org.id,
            proveedor_id=org.prov.deuda,
            tipo="ajuste",
            debe=pago.haber,
            ref_tipo=compras.REF_REVERSA,
            ref_id=pago.id,
            motivo="segunda, por atrás del service",
        )
    )
    with pytest.raises(IntegrityError):
        sesion.flush()


def test_prov_no_se_puede_revertir_una_compra(sesion, org):
    """Espeja un documento de compra: se corrige por su propio flujo, no desde el ledger."""
    compra = _primer_movimiento_prov(sesion, org.id, org.prov.deuda, "compra")

    with pytest.raises(compras.CompraInvalida, match="documento de compra"):
        compras.registrar_ajuste(
            sesion,
            org.id,
            proveedor_id=org.prov.deuda,
            motivo="anular la compra",
            revierte_movimiento_id=compra.id,
        )


def test_prov_no_se_puede_revertir_el_movimiento_de_otro_proveedor(sesion, org):
    ajeno = _primer_movimiento_prov(sesion, org.id, org.prov.favor, "pago")

    with pytest.raises(compras.CompraInvalida, match="No existe ese movimiento"):
        compras.registrar_ajuste(
            sesion,
            org.id,
            proveedor_id=org.prov.deuda,
            motivo="reversa cruzada",
            revierte_movimiento_id=ajeno.id,
        )


def test_prov_ajuste_manual_mueve_el_saldo_en_los_dos_sentidos(sesion, org):
    antes = compras.saldo_proveedor(sesion, org.id, org.prov.deuda)

    compras.registrar_ajuste(
        sesion, org.id, proveedor_id=org.prov.deuda, motivo="saldo inicial", debe=Decimal("400")
    )
    assert compras.saldo_proveedor(sesion, org.id, org.prov.deuda) == antes + Decimal("400")

    compras.registrar_ajuste(
        sesion, org.id, proveedor_id=org.prov.deuda, motivo="nos bonificaron", haber=Decimal("100")
    )
    assert compras.saldo_proveedor(sesion, org.id, org.prov.deuda) == antes + Decimal("300")


def test_prov_ajuste_manual_exige_exactamente_un_importe(sesion, org):
    with pytest.raises(compras.CompraInvalida, match="Debe o en Haber"):
        compras.registrar_ajuste(sesion, org.id, proveedor_id=org.prov.deuda, motivo="sin importe")

    with pytest.raises(compras.CompraInvalida, match="no en los dos"):
        compras.registrar_ajuste(
            sesion,
            org.id,
            proveedor_id=org.prov.deuda,
            motivo="los dos",
            debe=Decimal("10"),
            haber=Decimal("10"),
        )


def test_prov_ajuste_sin_motivo_se_rechaza(sesion, org):
    with pytest.raises(compras.CompraInvalida, match="motivo"):
        compras.registrar_ajuste(
            sesion, org.id, proveedor_id=org.prov.deuda, motivo="   ", debe=Decimal("10")
        )


def test_prov_el_check_de_la_base_exige_motivo_en_los_ajustes(sesion, org):
    sesion.add(
        ProvCtaCteMovimiento(
            org_id=org.id, proveedor_id=org.prov.deuda, tipo="ajuste", debe=Decimal("100")
        )
    )
    with pytest.raises(IntegrityError):
        sesion.flush()


def test_prov_ajuste_a_proveedor_inexistente_se_rechaza(sesion, org):
    with pytest.raises(compras.CompraInvalida, match="No existe ese proveedor"):
        compras.registrar_ajuste(
            sesion, org.id, proveedor_id=999999, motivo="fantasma", debe=Decimal("10")
        )


def test_prov_el_extracto_dice_que_se_puede_revertir(sesion, org):
    """El ledger sembrado de PROV-DEUDA tiene compras y un pago."""
    filas, _ = compras.movimientos_proveedor(sesion, org.id, org.prov.deuda, limite=100)
    por_tipo = {f.tipo: f.reversible for f in filas}

    assert por_tipo["pago"] is True
    assert por_tipo["compra"] is False  # espeja un documento de compra


def test_prov_un_movimiento_ya_revertido_deja_de_ser_reversible(sesion, org):
    pago = compras.registrar_pago(
        sesion, org.id, proveedor_codigo="PROV-DEUDA", monto=Decimal("90")
    )
    compras.registrar_ajuste(
        sesion,
        org.id,
        proveedor_id=org.prov.deuda,
        motivo="duplicado",
        revierte_movimiento_id=pago.id,
    )

    filas, _ = compras.movimientos_proveedor(sesion, org.id, org.prov.deuda, limite=100)
    assert {f.id: f.reversible for f in filas}[pago.id] is False


def test_prov_el_extracto_marca_anulado_y_trae_el_motivo(sesion, org):
    pago = compras.registrar_pago(
        sesion, org.id, proveedor_codigo="PROV-DEUDA", monto=Decimal("600")
    )
    ajuste = compras.registrar_ajuste(
        sesion,
        org.id,
        proveedor_id=org.prov.deuda,
        motivo="duplicado",
        revierte_movimiento_id=pago.id,
    )

    filas, _ = compras.movimientos_proveedor(sesion, org.id, org.prov.deuda, limite=100)
    por_id = {f.id: f for f in filas}

    assert por_id[pago.id].anulado is True
    assert por_id[ajuste.id].anulado is False
    assert por_id[ajuste.id].motivo == "duplicado"
    assert por_id[pago.id].motivo is None


# ==================================================================== fecha del movimiento


def test_una_cobranza_retroactiva_no_cambia_el_saldo_pero_si_reordena(sesion, org):
    """EL test de esta feature, y son las dos mitades de la misma verdad.

    `cliente_saldo` es SUM(debe) - SUM(haber): una suma NO depende del orden, así que fechar para
    atrás no puede mover el saldo final. Lo que sí se mueve son los acumulados intermedios del
    extracto, porque la window ordena por (fecha, id) y la fila se inserta en el medio. Eso no es
    un efecto colateral: es exactamente lo que significa fechar para atrás.
    """
    antes_saldo = service.saldo_cliente(sesion, org.id, org.cli.deuda)
    antes_filas, _ = service.movimientos_cliente(sesion, org.id, org.cli.deuda, limite=100)

    # El 2026-02-20 cae entre la cobranza del 15/02 y la venta del 20/03 del ledger sembrado.
    _cobrar(
        sesion,
        org.id,
        cliente_codigo="CLI-DEUDA",
        monto=Decimal("100"),
        fecha=date(2026, 2, 20),
    )

    # 1) El saldo final no se enteró del orden.
    assert service.saldo_cliente(sesion, org.id, org.cli.deuda) == antes_saldo - Decimal("100")

    # 2) Pero la fila entró en el MEDIO, no arriba (las filas vuelven DESC).
    despues, _ = service.movimientos_cliente(sesion, org.id, org.cli.deuda, limite=100)
    fechas = [f.fecha for f in despues]
    assert fechas == sorted(fechas, reverse=True), "el extracto tiene que seguir cronológico"
    assert despues[0].fecha != date(2026, 2, 20), "no puede haber quedado arriba de todo"

    # 3) Y los acumulados POSTERIORES a esa fecha se corrieron 100.
    viejos = {f.id: f.saldo_acumulado for f in antes_filas}
    corridos = [f for f in despues if f.id in viejos and f.saldo_acumulado != viejos[f.id]]
    assert corridos, "algún acumulado tenía que moverse"
    assert all(viejos[f.id] - f.saldo_acumulado == Decimal("100") for f in corridos)


def test_una_cobranza_sin_fecha_sigue_saliendo_con_la_de_hoy(sesion, org):
    """No romper lo que ya andaba: `fecha` es opcional y el default de la tabla manda."""
    mov = _cobrar(sesion, org.id, cliente_codigo="CLI-DEUDA", monto=Decimal("10"))
    assert mov.fecha == hoy()


def test_el_service_acepta_fechas_viejas_porque_es_el_camino_del_importador(sesion, org):
    """La ventana de 90 días es política de la API, NO del dominio.

    El importador de Paradox va a cargar años de historia por acá, así que el service no puede
    tener el límite. Por HTTP la misma fecha da 422 (ver el test del endpoint).
    """
    mov = _cobrar(
        sesion,
        org.id,
        cliente_codigo="CLI-DEUDA",
        monto=Decimal("10"),
        fecha=date(2020, 3, 1),
    )
    assert mov.fecha == date(2020, 3, 1)


def test_un_ajuste_tambien_puede_fecharse(sesion, org):
    """Un saldo inicial de migración no es de hoy."""
    ajuste = service.registrar_ajuste(
        sesion,
        org.id,
        cliente_id=org.cli.deuda,
        motivo="saldo inicial Paradox",
        debe=Decimal("500"),
        fecha=date(2026, 1, 2),
    )
    assert ajuste.fecha == date(2026, 1, 2)


def test_el_extracto_trae_cuando_se_cargo_ademas_de_cuando_paso(sesion, org):
    """Sin `creado_en` el retroactivo sería una forma prolija de reescribir el pasado: nadie
    podría ver que esa fila entró días después de la fecha que dice."""
    mov = _cobrar(
        sesion,
        org.id,
        cliente_codigo="CLI-DEUDA",
        monto=Decimal("10"),
        fecha=date(2026, 2, 20),
    )

    filas, _ = service.movimientos_cliente(sesion, org.id, org.cli.deuda, limite=100)
    fila = {f.id: f for f in filas}[mov.id]

    assert fila.fecha == date(2026, 2, 20)
    assert fila.creado_en.date() == hoy()  # se cargó HOY, aunque diga febrero


def test_prov_un_pago_retroactivo_no_cambia_el_saldo(sesion, org):
    antes = compras.saldo_proveedor(sesion, org.id, org.prov.deuda)

    compras.registrar_pago(
        sesion,
        org.id,
        proveedor_codigo="PROV-DEUDA",
        monto=Decimal("100"),
        fecha=date(2026, 3, 1),
    )

    assert compras.saldo_proveedor(sesion, org.id, org.prov.deuda) == antes - Decimal("100")

    filas, _ = compras.movimientos_proveedor(sesion, org.id, org.prov.deuda, limite=100)
    fechas = [f.fecha for f in filas]
    assert fechas == sorted(fechas, reverse=True)


# =========================================================================== ajustes (storno)


def _primer_movimiento(sesion, org_id, cliente_id, tipo) -> CtaCteMovimiento:
    """El movimiento más viejo de ese tipo en la cuenta: algo concreto que revertir."""
    mov = sesion.scalars(
        select(CtaCteMovimiento)
        .where(
            CtaCteMovimiento.org_id == org_id,
            CtaCteMovimiento.cliente_id == cliente_id,
            CtaCteMovimiento.tipo == tipo,
        )
        .order_by(CtaCteMovimiento.id)
    ).first()
    assert mov is not None, f"el fixture tiene que sembrar un movimiento {tipo!r}"
    return mov


def test_storno_deja_el_saldo_igual_que_antes_de_la_cobranza(sesion, org):
    """EL test de esta feature: la reversa cierra EXACTO contra la vista de saldo.

    Es la razón por la que el ajuste existe — una cobranza mal cargada no se puede editar (el
    ledger es append-only), así que la única prueba que importa es que el contra-movimiento
    devuelva el saldo al valor que tenía antes del error.
    """
    antes = service.saldo_cliente(sesion, org.id, org.cli.deuda)

    cobranza = _cobrar(sesion, org.id, cliente_codigo="CLI-DEUDA", monto=Decimal("5000"))
    assert service.saldo_cliente(sesion, org.id, org.cli.deuda) == antes - Decimal("5000")

    service.registrar_ajuste(
        sesion,
        org.id,
        cliente_id=org.cli.deuda,
        motivo="cobranza cargada dos veces",
        revierte_movimiento_id=cobranza.id,
    )
    assert service.saldo_cliente(sesion, org.id, org.cli.deuda) == antes


def test_storno_espeja_el_monto_y_referencia_el_original(sesion, org):
    """El importe lo calcula el SERVICE desde el original: nunca viaja en el pedido."""
    cobranza = _primer_movimiento(sesion, org.id, org.cli.deuda, "cobranza")

    ajuste = service.registrar_ajuste(
        sesion,
        org.id,
        cliente_id=org.cli.deuda,
        motivo="duplicada",
        revierte_movimiento_id=cobranza.id,
    )

    assert ajuste.tipo == "ajuste"
    assert ajuste.debe == cobranza.haber  # el haber vuelve como debe
    assert ajuste.haber == cobranza.debe
    assert (ajuste.ref_tipo, ajuste.ref_id) == (service.REF_REVERSA, cobranza.id)
    assert ajuste.motivo == "duplicada"


def test_el_acumulado_del_extracto_vuelve_al_valor_previo(sesion, org):
    """Ata la window function del extracto a la vista: las dos tienen que ver la reversa igual."""
    cobranza = _cobrar(sesion, org.id, cliente_codigo="CLI-DEUDA", monto=Decimal("777"))
    service.registrar_ajuste(
        sesion,
        org.id,
        cliente_id=org.cli.deuda,
        motivo="mal cargada",
        revierte_movimiento_id=cobranza.id,
    )

    filas, _ = service.movimientos_cliente(sesion, org.id, org.cli.deuda, limite=1)
    assert filas[0].saldo_acumulado == service.saldo_cliente(sesion, org.id, org.cli.deuda)


def test_no_se_puede_revertir_dos_veces_el_mismo_movimiento(sesion, org):
    """Revertir dos veces duplicaría la corrección, y en un ledger append-only no hay vuelta."""
    cobranza = _primer_movimiento(sesion, org.id, org.cli.deuda, "cobranza")
    service.registrar_ajuste(
        sesion,
        org.id,
        cliente_id=org.cli.deuda,
        motivo="primera",
        revierte_movimiento_id=cobranza.id,
    )

    with pytest.raises(service.VentaInvalida, match="ya fue revertido"):
        service.registrar_ajuste(
            sesion,
            org.id,
            cliente_id=org.cli.deuda,
            motivo="segunda",
            revierte_movimiento_id=cobranza.id,
        )


def test_el_indice_unico_ataja_la_doble_reversa_simultanea(sesion, org):
    """La garantía REAL no es el chequeo del service: es el índice parcial de la 0009.

    Se saltea el service a propósito, porque eso es exactamente lo que pasa cuando dos requests
    pasan el chequeo previo antes de que cualquiera de los dos haya insertado.
    """
    cobranza = _primer_movimiento(sesion, org.id, org.cli.deuda, "cobranza")
    service.registrar_ajuste(
        sesion,
        org.id,
        cliente_id=org.cli.deuda,
        motivo="primera",
        revierte_movimiento_id=cobranza.id,
    )

    sesion.add(
        CtaCteMovimiento(
            org_id=org.id,
            cliente_id=org.cli.deuda,
            tipo="ajuste",
            debe=cobranza.haber,
            ref_tipo=service.REF_REVERSA,
            ref_id=cobranza.id,
            motivo="segunda, por atrás del service",
        )
    )
    with pytest.raises(IntegrityError):
        sesion.flush()


def test_un_ajuste_si_se_puede_revertir(sesion, org):
    """Deshacer una corrección equivocada tiene que ser posible: si no, el ajuste sería una
    trampa de un solo sentido."""
    ajuste = service.registrar_ajuste(
        sesion, org.id, cliente_id=org.cli.deuda, motivo="condonación", haber=Decimal("400")
    )
    antes = service.saldo_cliente(sesion, org.id, org.cli.deuda)

    service.registrar_ajuste(
        sesion,
        org.id,
        cliente_id=org.cli.deuda,
        motivo="me equivoqué de cliente",
        revierte_movimiento_id=ajuste.id,
    )

    assert service.saldo_cliente(sesion, org.id, org.cli.deuda) == antes + Decimal("400")


@pytest.mark.parametrize("tipo", ["venta", "nota_credito"])
def test_no_se_puede_revertir_un_movimiento_de_comprobante(sesion, org, tipo):
    """Un movimiento que espeja un comprobante NO se revierte desde el ledger: dejaría el
    comprobante vivo con su cuenta corriente en cero y el ledger dejaría de espejarlo, en
    silencio. Se revierte con una nota de crédito."""
    mov = _primer_movimiento(sesion, org.id, org.cli.deuda, tipo)

    with pytest.raises(service.VentaInvalida, match="nota de crédito"):
        service.registrar_ajuste(
            sesion,
            org.id,
            cliente_id=org.cli.deuda,
            motivo="quiero anular la venta",
            revierte_movimiento_id=mov.id,
        )


def test_no_se_puede_revertir_el_movimiento_de_otro_cliente(sesion, org):
    """El filtro por cliente no es redundante con el de org: sin él se podría revertir la
    cobranza de otro cliente de la misma organización pasando su id a mano."""
    ajeno = _primer_movimiento(sesion, org.id, org.cli.favor, "cobranza")

    with pytest.raises(service.VentaInvalida, match="No existe ese movimiento"):
        service.registrar_ajuste(
            sesion,
            org.id,
            cliente_id=org.cli.deuda,
            motivo="reversa cruzada",
            revierte_movimiento_id=ajeno.id,
        )


def test_no_se_puede_revertir_un_movimiento_de_otra_org(sesion, org):
    with pytest.raises(service.VentaInvalida, match="No existe ese movimiento"):
        service.registrar_ajuste(
            sesion,
            org.id,
            cliente_id=org.cli.deuda,
            motivo="cruce de tenants",
            revierte_movimiento_id=999999,
        )


def test_la_reversa_no_acepta_importe(sesion, org):
    """Si el importe pudiera venir de afuera, se podría errar tipeando justo el número que se
    está corrigiendo."""
    cobranza = _primer_movimiento(sesion, org.id, org.cli.deuda, "cobranza")

    with pytest.raises(service.VentaInvalida, match="no lleva importe"):
        service.registrar_ajuste(
            sesion,
            org.id,
            cliente_id=org.cli.deuda,
            motivo="con monto a mano",
            revierte_movimiento_id=cobranza.id,
            debe=Decimal("1"),
        )


def test_ajuste_manual_mueve_el_saldo_en_los_dos_sentidos(sesion, org):
    antes = service.saldo_cliente(sesion, org.id, org.cli.deuda)

    service.registrar_ajuste(
        sesion,
        org.id,
        cliente_id=org.cli.deuda,
        motivo="saldo inicial Paradox",
        debe=Decimal("250"),
    )
    assert service.saldo_cliente(sesion, org.id, org.cli.deuda) == antes + Decimal("250")

    service.registrar_ajuste(
        sesion, org.id, cliente_id=org.cli.deuda, motivo="condonación", haber=Decimal("50")
    )
    assert service.saldo_cliente(sesion, org.id, org.cli.deuda) == antes + Decimal("200")


def test_ajuste_manual_exige_exactamente_un_importe(sesion, org):
    with pytest.raises(service.VentaInvalida, match="Debe o en Haber"):
        service.registrar_ajuste(sesion, org.id, cliente_id=org.cli.deuda, motivo="sin importe")

    with pytest.raises(service.VentaInvalida, match="no en los dos"):
        service.registrar_ajuste(
            sesion,
            org.id,
            cliente_id=org.cli.deuda,
            motivo="los dos",
            debe=Decimal("10"),
            haber=Decimal("10"),
        )


def test_ajuste_manual_rechaza_importe_no_positivo(sesion, org):
    with pytest.raises(service.VentaInvalida, match="mayor a cero"):
        service.registrar_ajuste(
            sesion, org.id, cliente_id=org.cli.deuda, motivo="cero", debe=Decimal("0")
        )


def test_ajuste_sin_motivo_se_rechaza(sesion, org):
    """Un ajuste sin motivo es una fila que en seis meses nadie puede explicar."""
    for motivo in ("", "   "):
        with pytest.raises(service.VentaInvalida, match="motivo"):
            service.registrar_ajuste(
                sesion, org.id, cliente_id=org.cli.deuda, motivo=motivo, debe=Decimal("10")
            )


def test_el_check_de_la_base_exige_motivo_en_los_ajustes(sesion, org):
    """El service valida, pero el que MANDA es el CHECK de la 0009: cualquier camino futuro al
    ledger (importador, script, otro service) se lleva el error igual."""
    sesion.add(
        CtaCteMovimiento(
            org_id=org.id, cliente_id=org.cli.deuda, tipo="ajuste", debe=Decimal("100")
        )
    )
    with pytest.raises(IntegrityError):
        sesion.flush()


def test_el_check_no_molesta_a_los_movimientos_automaticos(sesion, org):
    """Una cobranza no lleva motivo y tiene que seguir entrando sin problema."""
    _cobrar(sesion, org.id, cliente_codigo="CLI-DEUDA", monto=Decimal("1"))


def test_ajuste_a_cliente_inexistente_se_rechaza(sesion, org):
    with pytest.raises(service.VentaInvalida, match="No existe ese cliente"):
        service.registrar_ajuste(
            sesion, org.id, cliente_id=999999, motivo="fantasma", debe=Decimal("10")
        )


def test_el_extracto_marca_anulado_solo_el_movimiento_revertido(sesion, org):
    """Sin este flag el extracto muestra un haber y su contra-debe sin ninguna pista de que se
    cancelan entre sí, y el operador tiene que adivinar."""
    cobranza = _cobrar(sesion, org.id, cliente_codigo="CLI-DEUDA", monto=Decimal("900"))
    ajuste = service.registrar_ajuste(
        sesion,
        org.id,
        cliente_id=org.cli.deuda,
        motivo="duplicada",
        revierte_movimiento_id=cobranza.id,
    )

    filas, _ = service.movimientos_cliente(sesion, org.id, org.cli.deuda, limite=100)
    por_id = {f.id: f for f in filas}

    assert por_id[cobranza.id].anulado is True
    # La reversa NO está anulada: nadie la revirtió a ella.
    assert por_id[ajuste.id].anulado is False
    assert all(not f.anulado for f in filas if f.id not in (cobranza.id,))


def test_el_extracto_dice_que_se_puede_revertir(sesion, org):
    """La regla de qué es reversible vive SOLO acá: el front no puede tener su propia copia.

    El ledger sembrado tiene venta, cobranza, venta, venta y nota de crédito.
    """
    filas, _ = service.movimientos_cliente(sesion, org.id, org.cli.deuda, limite=100)
    por_tipo = {f.tipo: f.reversible for f in filas}

    assert por_tipo["cobranza"] is True
    # Espejan un comprobante: se corrigen con una nota de crédito, no desde el ledger.
    assert por_tipo["venta"] is False
    assert por_tipo["nota_credito"] is False


def test_un_movimiento_ya_revertido_deja_de_ser_reversible(sesion, org):
    """EL caso que un flag "solo por tipo" se comería: la cobranza sigue siendo de un tipo
    reversible, pero revertirla de nuevo duplicaría la corrección."""
    cobranza = _cobrar(sesion, org.id, cliente_codigo="CLI-DEUDA", monto=Decimal("120"))
    filas, _ = service.movimientos_cliente(sesion, org.id, org.cli.deuda, limite=100)
    assert {f.id: f.reversible for f in filas}[cobranza.id] is True

    ajuste = service.registrar_ajuste(
        sesion,
        org.id,
        cliente_id=org.cli.deuda,
        motivo="duplicada",
        revierte_movimiento_id=cobranza.id,
    )

    filas, _ = service.movimientos_cliente(sesion, org.id, org.cli.deuda, limite=100)
    por_id = {f.id: f for f in filas}
    assert por_id[cobranza.id].reversible is False
    # La reversa sí se puede revertir: deshacer una corrección equivocada tiene que ser posible.
    assert por_id[ajuste.id].reversible is True


def test_el_extracto_trae_el_motivo_del_ajuste(sesion, org):
    service.registrar_ajuste(
        sesion,
        org.id,
        cliente_id=org.cli.deuda,
        motivo="redondeo de centavos",
        haber=Decimal("0.03"),
    )

    filas, _ = service.movimientos_cliente(sesion, org.id, org.cli.deuda, limite=1)
    assert filas[0].motivo == "redondeo de centavos"
    # Los automáticos siguen sin motivo, y eso es correcto.
    assert all(f.motivo is None for f in filas[1:] if f.tipo != "ajuste")


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


def test_endpoint_cuenta_corriente_proveedores_shape(cliente):
    r = cliente.get("/compras/cuenta-corriente?limite=1")
    assert r.status_code == 200
    body = r.json()

    assert set(body) == {"items", "total", "saldo_total"}
    assert body["total"] == 2
    # Mismas claves que la de clientes: el front tiene UN schema para las dos solapas.
    assert set(body["items"][0]) == {"id", "codigo", "nombre", "saldo", "limite"}


def test_endpoint_movimientos_proveedor_shape(cliente, org):
    r = cliente.get(f"/compras/proveedores/{org.prov.deuda}/movimientos")
    assert r.status_code == 200
    body = r.json()

    assert set(body) == {"items", "total", "cuenta"}
    assert body["total"] == len(LEDGER_PROV)
    assert body["cuenta"]["codigo"] == "PROV-DEUDA"
    assert body["cuenta"]["saldo"] == "2500.00"
    assert body["cuenta"]["limite"] is None


def test_endpoint_movimientos_de_proveedor_inexistente_404(cliente):
    assert cliente.get("/compras/proveedores/999999/movimientos").status_code == 404


def test_endpoint_pago_registra_y_devuelve_saldo(cliente, org):
    """El POST existía desde el slice 3 y no tenía un solo test HTTP."""
    antes = Decimal(
        cliente.get(f"/compras/proveedores/{org.prov.deuda}/movimientos").json()["cuenta"]["saldo"]
    )

    r = cliente.post("/compras/pagos", json={"proveedor_codigo": "PROV-DEUDA", "monto": "500.00"})
    assert r.status_code == 201

    assert Decimal(r.json()["saldo"]) == antes - Decimal("500")


def test_endpoint_pago_monto_cero_es_422(cliente):
    r = cliente.post("/compras/pagos", json={"proveedor_codigo": "PROV-DEUDA", "monto": "0"})
    assert r.status_code == 422


# ------------------------------------------------------------------------ ajustes por HTTP
# Estos SÍ commitean (lo hace `get_tenant`), así que van al final y leen el saldo antes de tocarlo.


def _url_ajustes(cliente_id: int) -> str:
    return f"/ventas/clientes/{cliente_id}/ajustes"


def test_endpoint_ajuste_revierte_una_cobranza_de_punta_a_punta(cliente, org):
    """El recorrido completo del bug que motivó la feature: se carga una cobranza mal, se
    revierte, y el saldo vuelve exactamente a donde estaba."""
    antes = Decimal(
        cliente.get(f"/ventas/clientes/{org.cli.deuda}/movimientos").json()["cuenta"]["saldo"]
    )

    cobranza = cliente.post(
        "/ventas/cobranzas", json={"cliente_codigo": "CLI-DEUDA", "monto": "1234.56"}
    ).json()

    r = cliente.post(
        _url_ajustes(org.cli.deuda),
        json={"revierte_movimiento_id": cobranza["movimiento_id"], "motivo": "cargada dos veces"},
    )
    assert r.status_code == 201
    assert Decimal(r.json()["saldo"]) == antes

    # Y el extracto marca la cobranza como anulada.
    items = cliente.get(f"/ventas/clientes/{org.cli.deuda}/movimientos").json()["items"]
    anulada = next(m for m in items if m["id"] == cobranza["movimiento_id"])
    assert anulada["anulado"] is True


def test_endpoint_extracto_expone_motivo_y_anulado(cliente, org):
    """Fija el contrato que consume el front: sin estas dos claves no puede pintar el estado."""
    r = cliente.post(
        _url_ajustes(org.cli.deuda), json={"debe": "10.00", "motivo": "saldo inicial Paradox"}
    )
    assert r.status_code == 201

    mov = cliente.get(f"/ventas/clientes/{org.cli.deuda}/movimientos").json()["items"][0]
    assert mov["motivo"] == "saldo inicial Paradox"
    assert mov["anulado"] is False
    # El front dibuja el botón con esto y nada más: no vuelve a decidir por tipo.
    assert mov["reversible"] is True
    assert isinstance(mov["debe"], str)  # la plata sigue viajando como string


def test_endpoint_ajuste_doble_reversa_es_422(cliente, org):
    cobranza = cliente.post(
        "/ventas/cobranzas", json={"cliente_codigo": "CLI-DEUDA", "monto": "10.00"}
    ).json()
    payload = {"revierte_movimiento_id": cobranza["movimiento_id"], "motivo": "primera"}

    assert cliente.post(_url_ajustes(org.cli.deuda), json=payload).status_code == 201
    assert cliente.post(_url_ajustes(org.cli.deuda), json=payload).status_code == 422


def test_endpoint_ajuste_de_una_venta_es_422(cliente, org):
    venta = next(
        m
        for m in cliente.get(f"/ventas/clientes/{org.cli.deuda}/movimientos").json()["items"]
        if m["tipo"] == "venta"
    )

    r = cliente.post(
        _url_ajustes(org.cli.deuda),
        json={"revierte_movimiento_id": venta["id"], "motivo": "anular la venta"},
    )
    assert r.status_code == 422
    assert "nota de crédito" in r.json()["detail"]


def test_endpoint_ajuste_de_cliente_inexistente_es_404(cliente):
    """El cliente va en el path: su ausencia es 404, no 422."""
    r = cliente.post(_url_ajustes(999999), json={"debe": "10.00", "motivo": "fantasma"})
    assert r.status_code == 404


@pytest.mark.parametrize(
    "payload",
    [
        pytest.param({"debe": "10.00"}, id="sin-motivo"),
        pytest.param({"debe": "10.00", "motivo": "no"}, id="motivo-muy-corto"),
        pytest.param({"motivo": "sin importe ni reversa"}, id="sin-modo"),
        pytest.param({"motivo": "los dos", "debe": "1", "haber": "1"}, id="debe-y-haber"),
        pytest.param(
            {"motivo": "reversa con monto", "revierte_movimiento_id": 1, "debe": "1"},
            id="reversa-con-importe",
        ),
        pytest.param({"motivo": "importe cero", "debe": "0"}, id="importe-cero"),
    ],
)
def test_endpoint_ajuste_payload_incoherente_es_422(cliente, org, payload):
    assert cliente.post(_url_ajustes(org.cli.deuda), json=payload).status_code == 422


def test_endpoint_ajuste_proveedor_revierte_un_pago(cliente, org):
    """El espejo completo por HTTP: mismo contrato contra el otro prefijo."""
    url = f"/compras/proveedores/{org.prov.deuda}/ajustes"
    antes = Decimal(
        cliente.get(f"/compras/proveedores/{org.prov.deuda}/movimientos").json()["cuenta"]["saldo"]
    )

    pago = cliente.post(
        "/compras/pagos", json={"proveedor_codigo": "PROV-DEUDA", "monto": "250.00"}
    ).json()

    r = cliente.post(
        url, json={"revierte_movimiento_id": pago["movimiento_id"], "motivo": "pago duplicado"}
    )
    assert r.status_code == 201
    assert Decimal(r.json()["saldo"]) == antes

    # Segunda reversa del mismo movimiento: rechazada.
    assert (
        cliente.post(
            url, json={"revierte_movimiento_id": pago["movimiento_id"], "motivo": "otra vez"}
        ).status_code
        == 422
    )


def test_endpoint_ajuste_proveedor_expone_motivo_y_anulado(cliente, org):
    r = cliente.post(
        f"/compras/proveedores/{org.prov.deuda}/ajustes",
        json={"debe": "15.00", "motivo": "saldo inicial del proveedor"},
    )
    assert r.status_code == 201

    mov = cliente.get(f"/compras/proveedores/{org.prov.deuda}/movimientos").json()["items"][0]
    assert mov["motivo"] == "saldo inicial del proveedor"
    assert mov["anulado"] is False
    # Mismas claves que en clientes: el front tiene UN schema para las dos solapas.
    assert mov["reversible"] is True


def test_endpoint_ajuste_proveedor_inexistente_es_404(cliente):
    r = cliente.post(
        "/compras/proveedores/999999/ajustes", json={"debe": "10.00", "motivo": "fantasma"}
    )
    assert r.status_code == 404


# ------------------------------------------------------- la ventana de fechas, por HTTP
# El límite vive en el schema, así que solo se prueba acá. El service no lo tiene a propósito.


def test_endpoint_cobranza_acepta_fecha_retroactiva(cliente, org):
    ayer = (hoy() - timedelta(days=3)).isoformat()

    r = cliente.post(
        "/ventas/cobranzas",
        json={"cliente_codigo": "CLI-DEUDA", "monto": "50.00", "fecha": ayer},
    )
    assert r.status_code == 201

    mov = next(
        m
        for m in cliente.get(f"/ventas/clientes/{org.cli.deuda}/movimientos").json()["items"]
        if m["id"] == r.json()["movimiento_id"]
    )
    assert mov["fecha"] == ayer
    # Y queda registrado que se cargó hoy, no hace tres días.
    assert mov["creado_en"].startswith(hoy().isoformat())


def test_endpoint_cobranza_rechaza_fecha_futura(cliente):
    manana = (hoy() + timedelta(days=1)).isoformat()
    r = cliente.post(
        "/ventas/cobranzas",
        json={"cliente_codigo": "CLI-DEUDA", "monto": "50.00", "fecha": manana},
    )
    assert r.status_code == 422


def test_endpoint_cobranza_el_borde_de_la_ventana(cliente):
    """Los dos lados del límite, porque un off-by-one acá se nota recién en producción."""
    justo = (hoy() - timedelta(days=DIAS_RETROACTIVIDAD)).isoformat()
    pasado = (hoy() - timedelta(days=DIAS_RETROACTIVIDAD + 1)).isoformat()

    ok = cliente.post(
        "/ventas/cobranzas",
        json={"cliente_codigo": "CLI-DEUDA", "monto": "1.00", "fecha": justo},
    )
    assert ok.status_code == 201

    tarde = cliente.post(
        "/ventas/cobranzas",
        json={"cliente_codigo": "CLI-DEUDA", "monto": "1.00", "fecha": pasado},
    )
    assert tarde.status_code == 422


def test_endpoint_ajuste_acepta_fecha(cliente, org):
    hace_una_semana = (hoy() - timedelta(days=7)).isoformat()

    r = cliente.post(
        f"/ventas/clientes/{org.cli.deuda}/ajustes",
        json={"debe": "20.00", "motivo": "saldo inicial migración", "fecha": hace_una_semana},
    )
    assert r.status_code == 201


def test_endpoint_pago_proveedor_acepta_y_valida_la_fecha(cliente):
    ayer = (hoy() - timedelta(days=1)).isoformat()
    manana = (hoy() + timedelta(days=1)).isoformat()

    assert (
        cliente.post(
            "/compras/pagos",
            json={"proveedor_codigo": "PROV-DEUDA", "monto": "20.00", "fecha": ayer},
        ).status_code
        == 201
    )
    assert (
        cliente.post(
            "/compras/pagos",
            json={"proveedor_codigo": "PROV-DEUDA", "monto": "20.00", "fecha": manana},
        ).status_code
        == 422
    )


# =========================================================== integración con Repu (NL2SQL)


def test_repu_consulta_deuda_a_proveedores_scopeado_por_rls(org, monkeypatch):
    """Con `proveedor_saldo` en el esquema, Repu puede responder "¿a quién le debo?".

    Antes solo conocía `cliente_saldo`: contestaba cuánto le deben a uno, pero no cuánto debe
    uno. El RLS lo encierra igual que en ventas: la org vecina no tiene proveedores con saldo.
    """

    def _fake_completar(system: str, user: str, *, proveedor: str = "groq") -> str:
        if "generador de SQL" in system:
            return "select count(*) as cantidad from proveedor_saldo where saldo > 0"
        return "Ahí tenés la deuda con proveedores."

    monkeypatch.setattr(llm, "completar", _fake_completar)

    ejec = asistente_service._hacer_ejecutor(org.id, uuid4())
    assert grafo.responder("a quién le debo", ejec)["filas"][0]["cantidad"] == 1

    ejec_vecina = asistente_service._hacer_ejecutor(org.vecina, uuid4())
    assert grafo.responder("a quién le debo", ejec_vecina)["filas"][0]["cantidad"] == 0


def test_esquema_documenta_las_dos_cuentas_corrientes(org):
    """El esquema es lo ÚNICO que el LLM ve: si una tabla no está acá, no existe para Repu."""
    for tabla in ("prov_cta_cte_movimientos", "proveedor_saldo", "compras", "compra_items"):
        assert tabla in ESQUEMA, f"{tabla} no está en el esquema del NL2SQL"
