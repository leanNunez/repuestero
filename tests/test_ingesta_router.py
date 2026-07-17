"""Los endpoints HTTP de la ingesta visual (slice 6).

Es la primera suite del repo que usa TestClient, y con motivo: lo que se verifica acá es
exactamente lo que NO se puede ver llamando al service — que cada falla aterrice en el
código de estado correcto y que ningún mensaje interno se filtre al cliente.

El LLM se mockea (`llm.extraer_de_imagen`): sin red, sin tokens.
"""

import base64
import json
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from types import SimpleNamespace
from uuid import uuid4

import jwt
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.asistente import llm, seguridad
from app.catalogo.models import Articulo, ListaPrecio
from app.core import db as core_db
from app.core.config import get_settings
from app.core.models import Organizacion
from app.inventario import service as inventario
from app.main import app
from tests.conftest import APP_URL, OWNER_URL

# Con relleno: `ExtraerRequest` exige min_length=100 en el base64, y una foto de verdad
# siempre lo supera. Un JPEG de 20 bytes es un artefacto de test, no una imagen.
_JPEG = b"\xff\xd8\xff\xe0\x00\x10JFIF\x00\x01\x01\x00\x00\x01\x00\x01\x00\x00" + b"\x00" * 200
_JPEG_B64 = base64.b64encode(_JPEG).decode()

_EXTRACCION_OK = json.dumps(
    {
        "proveedor_nombre": "Distribuidora Sur",
        "numero_remito": "R-0001",
        "renglones": [
            {
                "codigo": "ROUT-1",
                "descripcion": "BUJIA NGK BKR6E",
                "cantidad": "5",
                "costo_unitario": "4200",
                "confianza": 0.95,
            },
        ],
    }
)


@pytest.fixture(scope="module")
def org(migrated_db):
    org_id, user_id = uuid4(), uuid4()
    eng = create_engine(OWNER_URL)
    with Session(eng) as s:
        s.add(Organizacion(id=org_id, nombre="Org Router"))
        s.flush()
        s.execute(
            ListaPrecio.__table__.insert().values(org_id=org_id, codigo="MOST", nombre="Mostrador")
        )
        s.add(Articulo(org_id=org_id, codigo="EXISTE-1", detalle="FILTRO", costo=Decimal("100")))
        inventario.crear_deposito(s, org_id, codigo="CEN", nombre="Central")
        s.execute(
            __import__("app.core.models", fromlist=["Miembro"])
            .Miembro.__table__.insert()
            .values(org_id=org_id, user_id=user_id, rol="admin")
        )
        s.commit()
    eng.dispose()
    return SimpleNamespace(id=org_id, user=user_id)


@pytest.fixture
def cliente(org, monkeypatch):
    """TestClient con el JWT del usuario sembrado y la sesión apuntando a la DB de test."""
    monkeypatch.setattr(core_db, "SessionLocal", lambda: Session(create_engine(APP_URL)))
    seguridad._reset_strikes_para_tests()

    # El secreto y el audience salen de la config, no hardcodeados: si conftest los cambia,
    # el test sigue firmando con lo que la app realmente valida.
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


def _extraer(cliente, **kw):
    body = {"imagen_base64": _JPEG_B64, "mime": "image/jpeg", **kw}
    return cliente.post("/ingesta-visual/extraer", json=body)


# =========================================================== auth


def test_sin_token_es_401():
    """Antes que nada: nadie sin credenciales gasta un token de visión."""
    with TestClient(app) as c:
        r = c.post(
            "/ingesta-visual/extraer", json={"imagen_base64": _JPEG_B64, "mime": "image/jpeg"}
        )
    assert r.status_code == 401


# =========================================================== /extraer


def test_extraer_devuelve_la_propuesta(cliente, monkeypatch):
    monkeypatch.setattr(llm, "extraer_de_imagen", lambda *a, **k: _EXTRACCION_OK)

    r = _extraer(cliente)

    assert r.status_code == 200
    body = r.json()
    assert body["ya_procesado"] is False
    assert body["numero_remito"] == "R-0001"
    assert len(body["remito_hash"]) == 64
    (renglon,) = body["renglones"]
    assert renglon["accion"] == "alta"
    assert renglon["costo_unitario"] == "4200"  # plata como STRING, nunca float


def test_imagen_que_miente_sobre_su_tipo_es_422(cliente, monkeypatch):
    """El mime lo elige quien manda el request: decide la firma de los bytes."""
    llamadas = []
    monkeypatch.setattr(
        llm, "extraer_de_imagen", lambda *a, **k: llamadas.append(1) or _EXTRACCION_OK
    )

    r = _extraer(cliente, mime="image/png")  # bytes JPEG, dice PNG

    assert r.status_code == 422
    assert "dice ser" in r.json()["detail"]
    assert llamadas == []  # ni se llamó al modelo


def test_imagen_gigante_rebota_en_el_boundary(cliente, monkeypatch):
    """El techo está en Pydantic, sobre el string base64. Decodificar 500MB para después
    rechazarlos ES el DoS."""
    llamadas = []
    monkeypatch.setattr(
        llm, "extraer_de_imagen", lambda *a, **k: llamadas.append(1) or _EXTRACCION_OK
    )

    r = _extraer(cliente, imagen_base64="A" * 20_000_000)

    assert r.status_code == 422
    assert llamadas == []


def test_formato_no_aceptado_es_422(cliente):
    r = cliente.post(
        "/ingesta-visual/extraer",
        json={"imagen_base64": _JPEG_B64, "mime": "image/gif"},
    )
    assert r.status_code == 422


def test_modelo_ilegible_es_502_y_no_filtra_internals(cliente, monkeypatch):
    monkeypatch.setattr(llm, "extraer_de_imagen", lambda *a, **k: "no soy json")

    r = _extraer(cliente)

    assert r.status_code == 502
    assert "Repu no pudo leer la foto" in r.json()["detail"]
    assert "json" not in r.json()["detail"].lower()  # nada del error interno


def test_proveedor_caido_es_500_generico(cliente, monkeypatch):
    """Sin fallback multimodal: si OpenAI se cae, se dice que falló — sin exponer por qué."""

    def _explota(*a, **k):
        raise RuntimeError("openai: 401 invalid api key")

    monkeypatch.setattr(llm, "extraer_de_imagen", _explota)

    r = _extraer(cliente)

    assert r.status_code == 500
    assert r.json()["detail"] == "No pude procesar la imagen."
    assert "api key" not in r.text.lower()  # ← el secreto NO se filtra


# =========================================================== /confirmar


def _body_confirmar(hash_="a" * 64, **kw):
    return {
        "remito_hash": hash_,
        "deposito_codigo": "CEN",
        "renglones": [
            {"codigo": "ROUT-C1", "detalle": "BUJIA NGK", "cantidad": "5", "costo_unitario": "4200"}
        ],
        **kw,
    }


def test_confirmar_escribe_y_devuelve_el_resumen(cliente):
    r = cliente.post("/ingesta-visual/confirmar", json=_body_confirmar())

    assert r.status_code == 200
    body = r.json()
    assert body["articulos_creados"] == ["ROUT-C1"]
    assert body["movimientos"] == 1
    assert body["remito_id"] > 0


def test_confirmar_el_mismo_remito_dos_veces_es_409(cliente):
    """El doble click no duplica el stock, y el usuario recibe un mensaje que entiende."""
    cliente.post("/ingesta-visual/confirmar", json=_body_confirmar(hash_="b" * 64))
    r = cliente.post("/ingesta-visual/confirmar", json=_body_confirmar(hash_="b" * 64))

    assert r.status_code == 409
    assert "ya se cargó" in r.json()["detail"]


def test_deposito_inexistente_es_422_entendible(cliente):
    r = cliente.post(
        "/ingesta-visual/confirmar",
        json=_body_confirmar(hash_="c" * 64, deposito_codigo="NO-EXISTE"),
    )

    assert r.status_code == 422
    assert "depósito" in r.json()["detail"]


def test_hash_con_forma_invalida_es_422(cliente):
    """`remito_hash` tiene pattern de sha256: ata la escritura a una imagen concreta."""
    r = cliente.post("/ingesta-visual/confirmar", json=_body_confirmar(hash_="no-es-un-hash"))
    assert r.status_code == 422


def test_renglon_sin_codigo_es_422(cliente):
    """Un artículo sin código no tiene identidad. Lo frena Pydantic, no la DB."""
    r = cliente.post(
        "/ingesta-visual/confirmar",
        json=_body_confirmar(
            hash_="d" * 64,
            renglones=[{"codigo": "", "detalle": "X", "cantidad": "1", "costo_unitario": "1"}],
        ),
    )
    assert r.status_code == 422


def test_cantidad_cero_es_422(cliente):
    """Un movimiento de stock de 0 no significa nada. Se frena en el boundary."""
    r = cliente.post(
        "/ingesta-visual/confirmar",
        json=_body_confirmar(
            hash_="e" * 64,
            renglones=[{"codigo": "X", "detalle": "X", "cantidad": "0", "costo_unitario": "1"}],
        ),
    )
    assert r.status_code == 422


def test_remito_sin_renglones_es_422(cliente):
    r = cliente.post(
        "/ingesta-visual/confirmar", json=_body_confirmar(hash_="f" * 64, renglones=[])
    )
    assert r.status_code == 422
