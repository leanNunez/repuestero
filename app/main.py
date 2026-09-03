import logging
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from sqlalchemy.exc import OperationalError

from app.asistente.router import router as asistente_router
from app.caja.router import router as caja_router
from app.catalogo.router import router as catalogo_router
from app.clientes.router import router as clientes_router
from app.compatibilidad.router import router as compatibilidad_router
from app.compras.router import router as compras_router
from app.core import db
from app.core.config import get_settings
from app.core.ratelimit import limiter
from app.core.rls import TenantContext, get_tenant
from app.dashboard.router import router as dashboard_router
from app.ingesta_visual.router import router as ingesta_visual_router
from app.proveedores.router import router as proveedores_router
from app.ventas.router import router as ventas_router

logger = logging.getLogger(__name__)
_settings = get_settings()


@asynccontextmanager
async def lifespan(_app: FastAPI):
    # Chequeo de config, no de conectividad: si en prod no hay forma de validar un JWT, es
    # mejor enterarse acá (log al deployear) que cuando un reclutador no puede entrar. No
    # aborta el arranque — degradado (todo 503 en /auth) sigue siendo mejor que caído.
    if _settings.is_prod and not (_settings.supabase_jwks_url or _settings.supabase_jwt_secret):
        logger.critical(
            "Arrancando en producción SIN SUPABASE_JWKS_URL ni SUPABASE_JWT_SECRET — "
            "todo endpoint autenticado va a responder 503."
        )
    # A propósito NO se precargan acá los embeddings de injection ni se corren migraciones:
    # ambos eran llamadas a servicios externos (HF Inference API / Postgres) que, si fallaban,
    # se llevaban puesto el arranque entero. Ver app/asistente/seguridad.py::_asegurar_embeddings
    # y Dockerfile.
    yield


app = FastAPI(
    title="Repuestero",
    description="ERP AI-native multi-tenant para casas de repuestos",
    version="0.2.0",
    lifespan=lifespan,
    # Swagger es un manual de ataque gratis: se apaga en producción (skill web-security).
    docs_url=None if _settings.is_prod else "/docs",
    redoc_url=None if _settings.is_prod else "/redoc",
    openapi_url=None if _settings.is_prod else "/openapi.json",
)

# CORS: nunca "*" en prod. Se configura por env (ALLOWED_ORIGINS).
if _settings.is_prod and _settings.origins == ["*"]:
    logger.warning("ALLOWED_ORIGINS no configurada en producción — CORS abierto a *")
app.add_middleware(
    CORSMiddleware,
    allow_origins=_settings.origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Rate limiting (slowapi).
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

app.include_router(catalogo_router)
app.include_router(clientes_router)
app.include_router(compatibilidad_router)
app.include_router(asistente_router)
app.include_router(dashboard_router)
app.include_router(ingesta_visual_router)
app.include_router(ventas_router)
app.include_router(compras_router)
app.include_router(proveedores_router)
app.include_router(caja_router)


@app.exception_handler(OperationalError)
async def _db_no_disponible(_request: Request, exc: OperationalError) -> JSONResponse:
    # La base no responde (ej. Supabase pausada por inactividad, o el connect_timeout de
    # app/core/db.py cortando una conexión colgada). Es un estado TEMPORAL, no un bug de la
    # request: 503, no 500 — y sobre todo no 401, que en el front dispara bounceIf401 y patea
    # al usuario al login por un problema que no es suyo.
    logger.error("Base de datos no disponible: %s", exc)
    return JSONResponse(status_code=503, content={"detail": "Base de datos no disponible"})


@app.get("/health", tags=["infra"])
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/health/db", tags=["infra"])
@limiter.limit("10/minute")
def health_db(request: Request) -> dict[str, str]:
    """Distingue "el backend está caído" de "el backend está arriba pero la base no
    responde" (ej. Supabase pausada) — dos estados hoy indistinguibles desde /health, que
    no toca la base. Sin secreto: el resultado (booleano) ya lo revela el sitio andando o
    no, y un secreto acá impediría que la pantalla de arranque del front lo consulte."""
    db.ping()
    return {"status": "ok"}


@app.get("/me", tags=["auth"])
def me(tenant: TenantContext = Depends(get_tenant)) -> dict[str, str]:
    """Prueba el circuito completo: JWT → usuario → membresía → org → sesión con RLS."""
    return {"user_id": str(tenant.user_id), "org_id": str(tenant.org_id)}
