from decimal import Decimal

from fastapi import APIRouter, Depends, Query

from app.dashboard import schemas, service
from app.core.rls import TenantContext, get_tenant

router = APIRouter(prefix="/dashboard", tags=["dashboard"])


@router.get("/resumen", response_model=schemas.ResumenKPIs)
def resumen(tenant: TenantContext = Depends(get_tenant)) -> dict:
    return service.resumen(tenant.session, tenant.org_id)


@router.get("/reposicion", response_model=list[schemas.ReposicionItem])
def reposicion(tenant: TenantContext = Depends(get_tenant)) -> list[dict]:
    """Artículos que llegaron a su punto de pedido: qué reponer, ordenado por faltante."""
    return service.reposicion(tenant.session, tenant.org_id)


@router.get("/margenes", response_model=list[schemas.MargenItem])
def margenes(
    umbral: Decimal = Query(default=service.UMBRAL_MARGEN_DEFAULT, ge=0, le=100),
    tenant: TenantContext = Depends(get_tenant),
) -> list[dict]:
    """Margen real por artículo (peor entre listas), marcando los que caen bajo el umbral objetivo."""
    return service.margenes(tenant.session, tenant.org_id, umbral)
