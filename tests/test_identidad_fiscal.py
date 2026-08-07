"""Identidad fiscal: condición del emisor y documento del receptor (migración 0014).

Lo que no puede faltar acá son **los candados**: `app/core/cond_fiscal.py` y `app/core/arca.py`
tienen cada uno una copia congelada en el CHECK de la 0014. Nada las ata salvo estos tests. Si
alguien suma un valor en Python y se olvida de la migración, tiene que ponerse rojo acá y no en el
mostrador.

Las organizaciones se insertan con el rol `postgres` (`OWNER_URL`) y no con `app_user`: la policy
de RLS de `organizaciones` filtra por la org del GUC, así que crear una nueva desde `app_user` no
es lo que un test de esquema quiere estar peleando.
"""

from types import SimpleNamespace
from uuid import uuid4

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.clientes import service
from app.core.arca import DOC_TIPO_CUIT, DOC_TIPO_DNI, DOC_TIPO_SIN_IDENTIFICAR, DOC_TIPOS
from app.core.cond_fiscal import CONDICIONES_FISCALES_EMISOR
from app.core.db import ORG_GUC, set_guc
from app.core.documentos import documento_de
from app.core.models import Miembro, Organizacion
from tests.conftest import APP_URL, OWNER_URL

CUIT_OK = "30-71233445-9"


@pytest.fixture(scope="module")
def org(migrated_db):
    org_id, user_id = uuid4(), uuid4()
    eng = create_engine(OWNER_URL)
    with Session(eng) as s:
        s.add(Organizacion(id=org_id, nombre="Org Identidad Fiscal"))
        s.flush()
        s.add(Miembro(org_id=org_id, user_id=user_id, rol="admin"))
        s.commit()
    eng.dispose()
    return SimpleNamespace(id=org_id, user=user_id)


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


@pytest.fixture
def sesion_owner(migrated_db):
    """Sesión con el rol dueño, para tocar `organizaciones` sin pelear con RLS."""
    eng = create_engine(OWNER_URL)
    conn = eng.connect()
    trans = conn.begin()
    with Session(bind=conn) as s:
        yield s
    trans.rollback()
    conn.close()
    eng.dispose()


# --------------------------------------------------------------------------------------
# Los candados: Python ↔ base
# --------------------------------------------------------------------------------------


def test_las_condiciones_del_emisor_de_python_y_de_la_base_coinciden(sesion_owner):
    """EL CANDADO del emisor.

    `CONDICIONES_FISCALES_EMISOR` y el CHECK de la 0014 son dos copias de la misma lista. Si
    alguien agrega un valor en Python y se olvida de la migración, esto se pone rojo acá.
    """
    for condicion in sorted(CONDICIONES_FISCALES_EMISOR):
        sesion_owner.add(Organizacion(id=uuid4(), nombre=f"Org {condicion}", cond_fiscal=condicion))
        sesion_owner.flush()  # el CHECK se evalúa acá, no en el commit


def test_un_consumidor_final_no_puede_ser_emisor_ni_en_la_base(sesion_owner):
    """La reja está en la base, no solo en el `if` de `letra_de`.

    Un consumidor final no emite comprobantes, los recibe. Si esto solo viviera en Python, una
    organización mal configurada se guardaría sin chistar y el error saldría al facturar, con el
    cliente esperando en el mostrador.
    """
    sesion_owner.add(
        Organizacion(id=uuid4(), nombre="Org Imposible", cond_fiscal="CONSUMIDOR_FINAL")
    )
    with pytest.raises(IntegrityError, match="ck_organizaciones_cond_fiscal"):
        sesion_owner.flush()


def test_una_organizacion_puede_no_tener_condicion_fiscal(sesion_owner):
    """Nullable a propósito: inventarle una condición fiscal a una org es inventar un hecho fiscal.

    Las 6 organizaciones que existían al escribir la 0014 quedaron en NULL, y ninguna podía
    facturar igual porque tampoco tienen CUIT.
    """
    org = Organizacion(id=uuid4(), nombre="Org Sin Configurar")
    sesion_owner.add(org)
    sesion_owner.flush()

    assert org.cond_fiscal is None


@pytest.mark.parametrize("doc_tipo", sorted(DOC_TIPOS))
def test_los_tipos_de_documento_de_python_y_de_la_base_coinciden(sesion, org, doc_tipo):
    """EL CANDADO del receptor: `arca.DOC_TIPOS` contra el CHECK de la 0014."""
    cliente = service.alta_cliente(
        sesion,
        org.id,
        denominacion=f"Cliente doc {doc_tipo}",
        doc_tipo=doc_tipo,
        doc_nro="30111222",
    )
    sesion.flush()

    assert cliente.doc_tipo == doc_tipo


def test_un_tipo_de_documento_inventado_lo_frena_la_base(sesion, org):
    """Sin pasar por el service, que es el camino del importador y de cualquier script.

    El INSERT crudo levanta en el propio `execute`, no en un `flush` posterior: no hay unidad de
    trabajo del ORM que difiera nada.
    """
    with pytest.raises(IntegrityError, match="ck_clientes_doc_tipo"):
        sesion.execute(
            text(
                "insert into clientes "
                "(org_id, codigo, denominacion, cond_fiscal, doc_tipo, doc_nro) "
                "values (:org, 'CLI-DOC-MALO', 'Doc inventado', 'CONSUMIDOR_FINAL', 42, '30111222')"
            ),
            {"org": str(org.id)},
        )


def test_un_documento_a_medias_lo_frena_la_base(sesion, org):
    """Un tipo sin número no identifica a nadie; un número sin tipo no dice qué documento es."""
    with pytest.raises(IntegrityError, match="ck_clientes_doc_par"):
        sesion.execute(
            text(
                "insert into clientes (org_id, codigo, denominacion, cond_fiscal, doc_tipo) "
                "values (:org, 'CLI-DOC-MEDIAS', 'Doc a medias', 'CONSUMIDOR_FINAL', 96)"
            ),
            {"org": str(org.id)},
        )


# --------------------------------------------------------------------------------------
# El service valida antes que la base
# --------------------------------------------------------------------------------------


def test_el_service_rechaza_un_documento_a_medias_con_un_mensaje_legible(sesion, org):
    """El CHECK lo frena igual, pero con un `IntegrityError` que no dice cuál de los dos falta.

    Y el importador no pasa por el borde HTTP, así que el schema de Pydantic no lo alcanza.
    """
    with pytest.raises(ValueError, match="completo o no se carga"):
        service.alta_cliente(sesion, org.id, denominacion="A medias", doc_tipo=DOC_TIPO_DNI)


def test_el_service_rechaza_un_tipo_de_documento_inventado(sesion, org):
    with pytest.raises(ValueError, match="Tipo de documento inválido"):
        service.alta_cliente(
            sesion, org.id, denominacion="Tipo raro", doc_tipo=42, doc_nro="30111222"
        )


def test_un_cliente_nace_sin_documento_declarado(sesion, org):
    """El padrón existente quedó así: 1822 clientes con `doc_tipo`/`doc_nro` en NULL.

    No es un hueco — `documento_de` cae al CUIT, y solo si tampoco hay declara sin identificar.
    """
    cliente = service.alta_cliente(sesion, org.id, denominacion="Mostrador")

    assert cliente.doc_tipo is None
    assert cliente.doc_nro is None


# --------------------------------------------------------------------------------------
# Lo que el padrón real va a declarar
# --------------------------------------------------------------------------------------


def test_un_cliente_con_cuit_y_sin_documento_declara_su_cuit(sesion, org):
    """Los 1312 clientes con CUIT del padrón viajan correctos SIN backfill.

    Es la razón de que la 0014 no toque una sola fila: la precedencia de `documento_de` ya los
    resuelve. Este test es el que respalda esa decisión.
    """
    cliente = service.alta_cliente(sesion, org.id, denominacion="Inscripto", cuit=CUIT_OK)

    assert documento_de(doc_tipo=cliente.doc_tipo, doc_nro=cliente.doc_nro, cuit=cliente.cuit) == (
        DOC_TIPO_CUIT,
        "30712334459",
    )


def test_un_consumidor_final_sin_cuit_declara_sin_identificar(sesion, org):
    """509 del padrón están así, y es la verdad: el que compra sin identificarse es anónimo."""
    cliente = service.alta_cliente(sesion, org.id, denominacion="Mostrador anónimo")

    assert documento_de(doc_tipo=cliente.doc_tipo, doc_nro=cliente.doc_nro, cuit=cliente.cuit) == (
        DOC_TIPO_SIN_IDENTIFICAR,
        "0",
    )


def test_un_dni_cargado_le_gana_al_cuit_al_declarar(sesion, org):
    """El caso que motivó las dos columnas nuevas.

    Sin ellas, un consumidor final que da su DNI viajaba como anónimo aunque lo hubiera dado.
    """
    cliente = service.alta_cliente(
        sesion,
        org.id,
        denominacion="Con DNI",
        cuit=CUIT_OK,
        doc_tipo=DOC_TIPO_DNI,
        doc_nro="30111222",
    )

    assert documento_de(doc_tipo=cliente.doc_tipo, doc_nro=cliente.doc_nro, cuit=cliente.cuit) == (
        DOC_TIPO_DNI,
        "30111222",
    )
