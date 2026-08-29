"""PR 1 — que un evento degradante (base pausada, red que falla) no sea una caída total.

No usan la base de test: son unitarios sobre `ip_cliente`, el guard de auth sin configurar,
el handler de `OperationalError`, y el `connect_timeout` del engine.
"""

import asyncio
import time

import pytest
from fastapi import FastAPI, HTTPException, Request
from fastapi.testclient import TestClient
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from sqlalchemy import create_engine
from sqlalchemy.exc import OperationalError

from app import main as main_module
from app.core import security
from app.core.config import Settings
from app.core.ratelimit import ip_cliente, limiter
from app.main import _db_no_disponible, app

# ------------------------------------------------------------------------------- ip_cliente ---


def _request(headers: dict[str, str], client_host: str = "10.0.0.5") -> Request:
    scope = {
        "type": "http",
        "headers": [(k.lower().encode(), v.encode()) for k, v in headers.items()],
        "client": (client_host, 12345),
    }
    return Request(scope)


def test_ip_cliente_sin_proxy_usa_el_peer_directo():
    """Local / tests: sin X-Forwarded-For, no hay proxy en el medio."""
    assert ip_cliente(_request({})) == "10.0.0.5"


def test_ip_cliente_toma_la_entrada_DERECHA_de_x_forwarded_for():
    """La izquierda la declara el cliente (spoofeable); la derecha la agrega el último
    proxy que tocó el request — el de Render. Antes del fix se tomaba la izquierda."""
    req = _request({"X-Forwarded-For": "1.2.3.4, 5.6.7.8"})
    assert ip_cliente(req) == "5.6.7.8"
    assert ip_cliente(req) != "1.2.3.4"


def test_ip_cliente_con_una_sola_entrada():
    assert ip_cliente(_request({"X-Forwarded-For": "9.9.9.9"})) == "9.9.9.9"


def test_el_limiter_usa_ip_cliente_no_el_peer_crudo():
    """slowapi.util.get_remote_address ignora X-Forwarded-For (usa request.client.host a
    secas): con eso como key_func, todos los visitantes detrás del proxy de Render
    compartían un único bucket. Wiring, no comportamiento — el comportamiento lo prueba el
    test siguiente."""
    assert limiter._key_func is ip_cliente


def test_dos_visitantes_no_comparten_bucket():
    """De punta a punta, con un mini-app propio (sin auth/DB de por medio): dos IPs detrás
    del mismo peer TCP — como serían dos visitantes reales detrás del proxy de Render —
    consumen CADA UNA su propio límite, en vez de uno solo compartido entre todos."""
    mini_app = FastAPI()
    mini_limiter = Limiter(key_func=ip_cliente)
    mini_app.state.limiter = mini_limiter
    mini_app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

    @mini_app.get("/ping")
    @mini_limiter.limit("1/minute")
    def ping(request: Request):
        return {"ok": True}

    with TestClient(mini_app) as c:
        r1 = c.get("/ping", headers={"X-Forwarded-For": "1.1.1.1"})
        r2 = c.get("/ping", headers={"X-Forwarded-For": "1.1.1.1"})  # mismo bucket, ya gastado
        r3 = c.get("/ping", headers={"X-Forwarded-For": "2.2.2.2"})  # otro visitante, bucket propio

    assert r1.status_code == 200
    assert r2.status_code == 429
    assert r3.status_code == 200


# --------------------------------------------------------------- auth sin configurar → 503 ---


def test_sin_jwks_ni_secret_da_503_no_401_ni_500():
    """Es un error de CONFIGURACIÓN del servidor, no un token inválido. Un 401 acá dispara
    bounceIf401 en el front y deja al usuario en un loop de login que nunca puede funcionar."""
    settings = Settings(
        database_url="postgresql://x/y", supabase_jwks_url="", supabase_jwt_secret=""
    )
    with pytest.raises(HTTPException) as exc:
        security.get_current_user(creds=None, settings=settings)
    assert exc.value.status_code == 503


def test_con_secret_configurado_pero_sin_token_da_401():
    """Regresión: el guard de config no debe tapar el 401 legítimo por falta de token."""
    settings = Settings(
        database_url="postgresql://x/y", supabase_jwks_url="", supabase_jwt_secret="algo"
    )
    with pytest.raises(HTTPException) as exc:
        security.get_current_user(creds=None, settings=settings)
    assert exc.value.status_code == 401


# --------------------------------------------------------- handler global de OperationalError ---


def test_operational_error_da_503():
    exc = OperationalError("select 1", {}, Exception("connection refused"))
    resp = asyncio.run(_db_no_disponible(None, exc))
    assert resp.status_code == 503


# ------------------------------------------------------------------- connect_timeout real ---


def test_connect_timeout_corta_rapido_no_cuelga():
    """Sin connect_timeout, psycopg se cuelga al timeout del SO (~2 min) contra un host que
    no responde. 192.0.2.1 es TEST-NET-1 (RFC 5737): reservado, nunca ruteable — corta por
    timeout, no por rechazo de conexión, que es justo el escenario de una Supabase pausada."""
    eng = create_engine(
        "postgresql+psycopg://x:x@192.0.2.1:5432/x",
        connect_args={"connect_timeout": 1},
    )
    inicio = time.monotonic()
    with pytest.raises(OperationalError), eng.connect():
        pass
    transcurrido = time.monotonic() - inicio
    assert transcurrido < 8, f"tardó {transcurrido:.1f}s — el connect_timeout no está cortando"
    eng.dispose()


# ------------------------------------------------------------------------- /health/db ---


def test_health_db_ok_cuando_la_base_responde(migrated_db):
    with TestClient(app) as c:
        r = c.get("/health/db")
    assert r.status_code == 200
    assert r.json() == {"status": "ok"}


def test_health_db_da_503_sin_filtrar_detalle_si_la_base_no_responde(monkeypatch):
    """El mensaje del driver trae el host — no debe llegar al cliente."""

    def _falla(*, timeout_ms: int = 2000) -> None:
        raise OperationalError("select 1", {}, Exception("connection to server at 10.0.0.9 failed"))

    monkeypatch.setattr(main_module.db, "ping", _falla)
    with TestClient(app) as c:
        r = c.get("/health/db")
    assert r.status_code == 503
    assert "10.0.0.9" not in r.text
    assert "connection to server" not in r.text
