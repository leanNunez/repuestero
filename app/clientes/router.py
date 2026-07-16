from fastapi import APIRouter, Depends, Query

from app.clientes import service
from app.clientes.schemas import ClienteLeer
from app.core.rls import TenantContext, get_tenant

router = APIRouter(prefix="/clientes", tags=["clientes"])


@router.get("", response_model=list[ClienteLeer])
def listar(
    limite: int = Query(default=50, ge=1, le=200),
    tenant: TenantContext = Depends(get_tenant),
) -> list[ClienteLeer]:
    """Listado read-only de clientes de la org. El alta/cta cte es Fase 2."""
    clientes = service.listar_clientes(tenant.session, tenant.org_id, limite=limite)
    return [ClienteLeer.model_validate(c) for c in clientes]
