from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.catalogo import service
from app.catalogo.schemas import ArticuloLeer, ResultadoBusqueda
from app.core.rls import TenantContext, get_tenant

router = APIRouter(prefix="/catalogo", tags=["catalogo"])


@router.get("/buscar", response_model=list[ResultadoBusqueda])
def buscar(
    q: str = Query(min_length=1, max_length=120),
    limite: int = Query(default=20, ge=1, le=100),
    tenant: TenantContext = Depends(get_tenant),
) -> list[ResultadoBusqueda]:
    """Búsqueda híbrida: texto (full-text + typos) + significado (pgvector), fusionados por RRF.

    "filtro para el aceite del gol" encuentra el FILTRO DE ACEITE aunque no matcheen las palabras.
    """
    resultados = service.buscar_articulos(tenant.session, tenant.org_id, q=q, limite=limite)
    return [
        ResultadoBusqueda(**ArticuloLeer.model_validate(a).model_dump(), score=round(s, 6))
        for a, s in resultados
    ]


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
