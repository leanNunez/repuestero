from fastapi import APIRouter, Depends, Query

from app.core.rls import TenantContext, get_tenant
from app.proveedores import service
from app.proveedores.schemas import ProveedorLeer

router = APIRouter(prefix="/proveedores", tags=["proveedores"])


@router.get("", response_model=list[ProveedorLeer])
def listar(
    limite: int = Query(default=50, ge=1, le=200),
    tenant: TenantContext = Depends(get_tenant),
) -> list[ProveedorLeer]:
    """Listado read-only de proveedores de la org, para el selector de compras."""
    proveedores = service.listar_proveedores(tenant.session, tenant.org_id, limite=limite)
    return [ProveedorLeer.model_validate(p) for p in proveedores]
