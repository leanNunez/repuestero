import logging

from fastapi import Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded

from app.asistente import seguridad
from app.asistente.router import router as asistente_router
from app.catalogo.router import router as catalogo_router
from app.clientes.router import router as clientes_router
from app.compatibilidad.router import router as compatibilidad_router
from app.dashboard.router import router as dashboard_router
from app.ingesta_visual.router import router as ingesta_visual_router
from app.core.config import get_settings
from app.core.ratelimit import limiter
from app.core.rls import TenantContext, get_tenant

logger = logging.getLogger(__name__)
_settings = get_settings()

app = FastAPI(
    title="RepuestOS",
    description="ERP AI-native multi-tenant para casas de repuestos",
    version="0.2.0",
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


@app.on_event("startup")
def _startup() -> None:
    # Pre-computa los embeddings de injection UNA vez (no por request). Carga el modelo de fastembed.
    seguridad.precargar_embeddings()


@app.get("/health", tags=["infra"])
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/me", tags=["auth"])
def me(tenant: TenantContext = Depends(get_tenant)) -> dict[str, str]:
    """Prueba el circuito completo: JWT → usuario → membresía → org → sesión con RLS."""
    return {"user_id": str(tenant.user_id), "org_id": str(tenant.org_id)}
