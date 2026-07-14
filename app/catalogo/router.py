from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.catalogo import service
from app.catalogo.schemas import ArticuloLeer
from app.core.rls import TenantContext, get_tenant

router = APIRouter(prefix="/catalogo", tags=["catalogo"])


@router.get("/articulos", response_model=list[ArticuloLeer])
def listar_articulos(
    buscar: str | None = Query(default=None, max_length=80),
    limite: int = Query(default=50, ge=1, le=200),
    tenant: TenantContext = Depends(get_tenant),
) -> list[ArticuloLeer]:
    articulos = service.listar_articulos(
        tenant.session, tenant.org_id, buscar=buscar, limite=limite
    )
    return [ArticuloLeer.model_validate(a) for a in articulos]


@router.get("/articulos/{codigo}", response_model=ArticuloLeer)
def obtener_articulo(
    codigo: str,
    tenant: TenantContext = Depends(get_tenant),
) -> ArticuloLeer:
    articulo = service.obtener_articulo(tenant.session, tenant.org_id, codigo)
    if articulo is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Artículo no encontrado")
    return ArticuloLeer.model_validate(articulo)
