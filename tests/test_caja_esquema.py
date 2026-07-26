"""Las guardas que la base impone sobre caja y cheques (migración 0011).

Esto NO testea comportamiento: todavía no hay service. Testea que el ESQUEMA haga cumplir lo que
el diseño promete, porque `caja_movimientos` es append-only y un invariante que no se hace
cumplir acá es plata mal contada sin arreglo posible.

Lo que no puede faltar:
- Append-only de verdad (REVOKE + trigger) sobre el LIBRO, y que `cheques` en cambio SÍ acepte
  UPDATE (muta por diseño) pero NUNCA DELETE.
- Que un movimiento mueva exactamente UN lado, y que el concepto sea coherente con ese lado: sin
  eso el vocabulario es decorativo y los reportes por concepto mienten.
- Que el catálogo de conceptos de Python y el CHECK congelado en la migración no se separen.
- Que la vista `caja_saldo` respete el RLS (`security_invoker`), que es el bug que dejaría a un
  tenant ver la caja de otro.

Todo contra Postgres real, patrón A (app_user, sujeto a RLS).
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

from app.caja.models import CajaMovimiento, CajaSaldo, Cheque
from app.core.conceptos_caja import CONCEPTOS_EGRESO, CONCEPTOS_INGRESO
from app.core.db import ORG_GUC, set_guc
from app.core.formas_pago import FORMAS_PAGO
from app.core.models import Organizacion
from tests.conftest import APP_URL, OWNER_URL


@pytest.fixture(scope="module")
def org(migrated_db):
    """Una org, más una vecina con un movimiento de caja y un cheque que no deben verse."""
    org_id, vecina_id = uuid4(), uuid4()
    eng = create_engine(OWNER_URL)
    with Session(eng) as s:
        s.add(Organizacion(id=org_id, nombre="Org Caja"))
        s.add(Organizacion(id=vecina_id, nombre="Org Vecina Caja"))
        s.flush()

        vecino = CajaMovimiento(
            org_id=vecina_id,
            fecha=date(2026, 5, 1),
            ingreso=Decimal("99999"),
            forma="efectivo",
            concepto="aporte",
        )
        cheque_vecino = Cheque(
            org_id=vecina_id, origen="recibido", importe=Decimal("77777"), estado="en_cartera"
        )
        s.add_all([vecino, cheque_vecino])
        s.flush()
        ids = SimpleNamespace(mov_vecino=vecino.id, cheque_vecino=cheque_vecino.id)
        s.commit()
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


@contextmanager
def _rechaza(sesion, patron: str) -> Iterator[None]:
    """Espera que la BASE rechace lo de adentro, sin dejar la transacción abortada.

    El savepoint es lo que deja seguir usando la sesión después del error. Mismo patrón que
    `tests/test_recibos_esquema.py`.
    """
    sp = sesion.begin_nested()
    with pytest.raises(IntegrityError, match=patron):
        yield
    sp.rollback()


def _mov(
    sesion,
    org,
    *,
    ingreso: str = "0",
    egreso: str = "0",
    forma: str = "efectivo",
    concepto: str = "aporte",
    ref_tipo: str | None = None,
    ref_id: int | None = None,
) -> CajaMovimiento:
    m = CajaMovimiento(
        org_id=org.id,
        ingreso=Decimal(ingreso),
        egreso=Decimal(egreso),
        forma=forma,
        concepto=concepto,
        ref_tipo=ref_tipo,
        ref_id=ref_id,
    )
    sesion.add(m)
    sesion.flush()
    return m


def _cheque(sesion, org, *, importe: str = "15000", **kw) -> Cheque:
    c = Cheque(org_id=org.id, origen=kw.pop("origen", "recibido"), importe=Decimal(importe), **kw)
    sesion.add(c)
    sesion.flush()
    return c


# =========================================================================== append-only


def test_un_movimiento_de_caja_no_se_puede_editar(sesion, org):
    """La plata no se corrige editando: se carga el movimiento contrario."""
    m = _mov(sesion, org, ingreso="1000")

    sp = sesion.begin_nested()
    with pytest.raises(Exception, match="permission denied|no se edita"):
        sesion.execute(text("update caja_movimientos set ingreso = 1 where id = :i"), {"i": m.id})
    sp.rollback()

    sp = sesion.begin_nested()
    with pytest.raises(Exception, match="permission denied|no se edita"):
        sesion.execute(text("delete from caja_movimientos where id = :i"), {"i": m.id})
    sp.rollback()


def test_un_cheque_SI_se_puede_actualizar(sesion, org):
    """La excepción deliberada del módulo: el cheque muta porque el papel cambia de estado.

    Si esto fallara, la cartera no podría existir — no habría forma de pasar de 'en_cartera' a
    'depositado' sin borrar y reinsertar, que es peor.
    """
    c = _cheque(sesion, org)

    sesion.execute(text("update cheques set estado = 'depositado' where id = :i"), {"i": c.id})
    sesion.flush()

    assert sesion.scalar(select(Cheque.estado).where(Cheque.id == c.id)) == "depositado"


def test_un_cheque_NO_se_puede_borrar(sesion, org):
    """Un cheque que existió no desaparece: se marca rechazado o entregado."""
    c = _cheque(sesion, org)

    sp = sesion.begin_nested()
    with pytest.raises(Exception, match="permission denied"):
        sesion.execute(text("delete from cheques where id = :i"), {"i": c.id})
    sp.rollback()


# =========================================================================== un solo lado


def test_un_movimiento_tiene_que_mover_un_lado(sesion, org):
    """Un movimiento en cero es ruido en el libro.

    Se acepta cualquiera de los dos CHECKs: con los dos lados en cero fallan LOS DOS
    (`concepto_coherente` también exige que un lado sea > 0), y cuál reporta Postgres es orden de
    evaluación, no contrato. Pinear uno haría que el test se rompa por un cambio que no es suyo.
    """
    with _rechaza(sesion, "ck_caja_movimientos_(un_solo_lado|concepto_coherente)"):
        _mov(sesion, org, ingreso="0", egreso="0")


def test_un_movimiento_no_puede_mover_los_dos_lados(sesion, org):
    """Ingreso y egreso a la vez son DOS movimientos mal escritos."""
    with _rechaza(sesion, "ck_caja_movimientos_un_solo_lado"):
        _mov(sesion, org, ingreso="100", egreso="50", concepto="aporte")


# =========================================================================== concepto coherente


def test_un_concepto_de_egreso_no_puede_venir_como_ingreso(sesion, org):
    """El invariante que hace que el vocabulario sirva de algo.

    Sin este CHECK, 'gasto' podría entrar como ingreso y el reporte por concepto mentiría sin que
    nada se rompa — el peor tipo de error: silencioso y contable.
    """
    with _rechaza(sesion, "ck_caja_movimientos_concepto_coherente"):
        _mov(sesion, org, ingreso="500", concepto="gasto")


def test_un_concepto_de_ingreso_no_puede_venir_como_egreso(sesion, org):
    with _rechaza(sesion, "ck_caja_movimientos_concepto_coherente"):
        _mov(sesion, org, egreso="500", concepto="cobranza")


def test_el_check_rechaza_un_concepto_inventado(sesion, org):
    with _rechaza(sesion, "ck_caja_movimientos_concepto"):
        _mov(sesion, org, ingreso="100", concepto="propina")


def test_el_check_rechaza_una_forma_inventada(sesion, org):
    with _rechaza(sesion, "ck_caja_movimientos_forma"):
        _mov(sesion, org, ingreso="100", forma="bitcoin")


# =========================================================================== los catálogos atados


def test_los_conceptos_de_python_y_el_check_de_la_base_coinciden(sesion, org):
    """El candado de la constante compartida.

    `CONCEPTOS_*` vive en `app/core/conceptos_caja.py`, pero la 0011 congela su propia copia en el
    CHECK (una migración no puede importar código que cambia). Si alguien agrega un concepto en
    Python sin migrar, este test lo caza acá y no en producción.

    Además verifica la COHERENCIA de cada uno con su lado, que es la parte que un `in` suelto no
    probaría: cada concepto de ingreso entra como ingreso y cada uno de egreso como egreso.
    """
    for concepto in sorted(CONCEPTOS_INGRESO):
        _mov(sesion, org, ingreso="10", concepto=concepto)
    for concepto in sorted(CONCEPTOS_EGRESO):
        _mov(sesion, org, egreso="10", concepto=concepto)

    guardados = sesion.scalars(select(CajaMovimiento.concepto)).all()
    assert sorted(guardados) == sorted(CONCEPTOS_INGRESO | CONCEPTOS_EGRESO)


def test_las_formas_de_python_y_el_check_de_la_base_coinciden(sesion, org):
    """Mismo candado para el catálogo que caja COMPARTE con recibos y órdenes de pago."""
    for forma in sorted(FORMAS_PAGO):
        _mov(sesion, org, ingreso="10", forma=forma)

    guardadas = sesion.scalars(select(CajaMovimiento.forma)).all()
    assert sorted(guardadas) == sorted(FORMAS_PAGO)


# =========================================================================== referencias


def test_media_referencia_no_apunta_a_nada(sesion, org):
    """`ref_tipo` sin `ref_id` (o al revés) es un movimiento que dice venir de un documento que no
    se puede encontrar. O están los dos o no está ninguno."""
    with _rechaza(sesion, "ck_caja_movimientos_ref_completa"):
        _mov(sesion, org, ingreso="100", ref_tipo="recibo", ref_id=None)


def test_un_movimiento_manual_no_lleva_referencia(sesion, org):
    """El caso feliz del otro lado: manual = las dos en NULL, y la base lo acepta."""
    m = _mov(sesion, org, ingreso="100", concepto="aporte")

    assert m.ref_tipo is None
    assert m.ref_id is None


# =========================================================================== cheques


def test_un_cheque_no_puede_tener_importe_cero(sesion, org):
    with _rechaza(sesion, "ck_cheques_importe_positivo"):
        _cheque(sesion, org, importe="0")


def test_el_check_rechaza_un_estado_inventado(sesion, org):
    with _rechaza(sesion, "ck_cheques_estado"):
        _cheque(sesion, org, estado="extraviado")


def test_el_check_rechaza_un_origen_inventado(sesion, org):
    with _rechaza(sesion, "ck_cheques_origen"):
        _cheque(sesion, org, origen="encontrado")


def test_un_cheque_conciliado_necesita_fecha_de_conciliacion(sesion, org):
    """Una conciliación sin fecha no se puede auditar, que es todo el punto de conciliar."""
    with _rechaza(sesion, "ck_cheques_conciliado_con_fecha"):
        _cheque(sesion, org, conciliado=True, fecha_conciliacion=None)


def test_un_cheque_nace_en_cartera(sesion, org):
    """El default del esquema: quien lo inserta no tiene que acordarse del estado inicial."""
    c = _cheque(sesion, org)

    assert c.estado == "en_cartera"
    assert c.conciliado is False


# =========================================================================== saldo (la vista)


def test_el_saldo_es_la_suma_por_forma(sesion, org):
    """`caja_saldo` agrupa por forma: el cajón (efectivo) no se mezcla con lo que entró por
    transferencia. Es lo que hace que "cuánto hay en la caja" tenga una respuesta."""
    _mov(sesion, org, ingreso="5000", forma="efectivo", concepto="cobranza")
    _mov(sesion, org, egreso="1500", forma="efectivo", concepto="gasto")
    _mov(sesion, org, ingreso="20000", forma="transferencia", concepto="cobranza")
    sesion.flush()

    saldos = dict(sesion.execute(select(CajaSaldo.forma, CajaSaldo.saldo)).all())
    assert saldos["efectivo"] == Decimal("3500.00")
    assert saldos["transferencia"] == Decimal("20000.00")


def test_una_forma_sin_movimientos_no_aparece_en_la_vista(sesion, org):
    """Igual que `cliente_saldo`: la ausencia de fila ES el cero, y el service tiene que
    tratarla así en vez de asumir que la fila existe."""
    _mov(sesion, org, ingreso="100", forma="efectivo", concepto="aporte")
    sesion.flush()

    formas = sesion.scalars(select(CajaSaldo.forma)).all()
    assert "tarjeta" not in formas


# =========================================================================== aislamiento por org


def test_el_movimiento_de_otra_org_no_se_ve(sesion, org):
    assert sesion.get(CajaMovimiento, org.mov_vecino) is None
    assert sesion.scalars(select(CajaMovimiento)).all() == []


def test_el_cheque_de_otra_org_no_se_ve(sesion, org):
    assert sesion.get(Cheque, org.cheque_vecino) is None
    assert sesion.scalars(select(Cheque)).all() == []


def test_la_vista_de_saldo_respeta_el_rls(sesion, org):
    """El bug que `security_invoker = true` evita.

    Sin esa opción la vista corre con los permisos de SU OWNER y saltea el RLS de la tabla: la org
    vecina tiene 99.999 sembrados, y sin invoker aparecerían acá. Es la misma reja que
    `cliente_saldo`, y la que más caro sale olvidar porque no rompe nada — solo filtra plata
    ajena en silencio.
    """
    assert sesion.execute(select(CajaSaldo)).all() == []
