from fastapi import Depends, FastAPI

from app.catalogo.router import router as catalogo_router
from app.compatibilidad.router import router as compatibilidad_router
from app.core.rls import TenantContext, get_tenant

app = FastAPI(
    title="RepuestOS",
    description="ERP AI-native multi-tenant para casas de repuestos — Fase 0 (fundaciones)",
    version="0.1.0",
)

app.include_router(catalogo_router)
app.include_router(compatibilidad_router)


@app.get("/health", tags=["infra"])
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/me", tags=["auth"])
def me(tenant: TenantContext = Depends(get_tenant)) -> dict[str, str]:
    """Prueba el circuito completo: JWT → usuario → membresía → org → sesión con RLS."""
    return {"user_id": str(tenant.user_id), "org_id": str(tenant.org_id)}
