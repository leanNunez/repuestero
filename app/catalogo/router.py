from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.catalogo import service
from app.catalogo.schemas import ArticuloLeer, ArticuloPagina, ResultadoBusqueda
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


@router.get("/articulos", response_model=ArticuloPagina)
def listar_articulos(
    buscar: str | None = Query(default=None, max_length=80),
    rubro: str | None = Query(default=None, max_length=60),
    marca: str | None = Query(default=None, max_length=60),
    limite: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    tenant: TenantContext = Depends(get_tenant),
) -> ArticuloPagina:
    articulos, total = service.listar_articulos(
        tenant.session,
        tenant.org_id,
        buscar=buscar,
        rubro=rubro,
        marca=marca,
        limite=limite,
        offset=offset,
    )
    return ArticuloPagina(items=[ArticuloLeer.model_validate(a) for a in articulos], total=total)


@router.get("/rubros", response_model=list[str])
def listar_rubros(tenant: TenantContext = Depends(get_tenant)) -> list[str]:
    """Rubros distintos del catálogo del tenant, para poblar el filtro del listado."""
    return service.listar_rubros(tenant.session, tenant.org_id)


@router.get("/marcas", response_model=list[str])
def listar_marcas(tenant: TenantContext = Depends(get_tenant)) -> list[str]:
    """Marcas distintas del catálogo del tenant, para poblar el filtro del listado."""
    return service.listar_marcas(tenant.session, tenant.org_id)


@router.get("/articulos/{codigo}", response_model=ArticuloLeer)
def obtener_articulo(
    codigo: str,
    tenant: TenantContext = Depends(get_tenant),
) -> ArticuloLeer:
    articulo = service.obtener_articulo(tenant.session, tenant.org_id, codigo)
    if articulo is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Artículo no encontrado")
    return ArticuloLeer.model_validate(articulo)
