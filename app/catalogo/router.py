"""Endpoints del catálogo: búsqueda híbrida, listado paginado, detalle y alta de artículos.

El alta recibe el código del FABRICANTE tipeado por quien carga (a diferencia de clientes y
proveedores, donde lo genera el servidor): en repuestos es como el cliente pide la pieza en el
mostrador. La unicidad la arbitra `uq_articulos_org_codigo` y aterriza como 409. Los errores de
negocio del service (`ValueError`) se traducen a 422. Nunca se filtran internals (skill
web-security).
"""

import logging

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.exc import IntegrityError

from app.catalogo import service
from app.catalogo.schemas import (
    ArticuloAltaRequest,
    ArticuloAltaResponse,
    ArticuloCrear,
    ArticuloLeer,
    ArticuloPagina,
    ResultadoBusqueda,
)
from app.core.rls import TenantContext, get_tenant

logger = logging.getLogger(__name__)

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


@router.post(
    "/articulos",
    response_model=ArticuloAltaResponse,
    status_code=status.HTTP_201_CREATED,
)
def crear_articulo(
    body: ArticuloAltaRequest,
    tenant: TenantContext = Depends(get_tenant),
) -> ArticuloAltaResponse:
    """Da de alta un artículo. El código lo tipea quien carga; el precio de venta es opcional."""
    try:
        articulo, advertencias = service.alta_articulo(
            tenant.session,
            tenant.org_id,
            # El `exclude` no es cosmético: `ArticuloAltaRequest` HEREDA de `ArticuloCrear`, y
            # `crear_articulo` hace `Articulo(**datos.model_dump())`. Pasarlo derecho explotaría
            # con `precio`/`lista_id` de sobra —un bug latente de sustitución—. Cerrarlo en el
            # borde deja además la firma del service honesta: recibe datos de artículo más la
            # intención de precio, no un schema HTTP.
            datos=ArticuloCrear(**body.model_dump(exclude={"precio", "lista_id"})),
            precio=body.precio,
            lista_id=body.lista_id,
        )
    except ValueError as exc:
        # Código o detalle vacíos post-strip, montos negativos, alícuota fuera de rango, precio
        # sin lista, o una lista que no es de esta organización.
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, str(exc)) from None
    except IntegrityError as exc:
        # Choque de `uq_articulos_org_codigo`. El unique es el árbitro y no un `if` previo: entre
        # el chequeo y el insert hay una ventana donde otra transacción mete el mismo código.
        logger.info("Alta de artículo en conflicto (org=%s): %s", tenant.org_id, exc)
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            "Ya existe un artículo con ese código.",
        ) from None
    except Exception:  # noqa: BLE001 — nunca filtrar internals (skill web-security)
        logger.exception("Error en POST /catalogo/articulos")
        raise HTTPException(
            status.HTTP_500_INTERNAL_SERVER_ERROR,
            "No se pudo dar de alta el artículo.",
        ) from None

    return ArticuloAltaResponse(
        articulo=ArticuloLeer.model_validate(articulo),
        advertencias=advertencias,
    )


@router.get("/articulos/{codigo}", response_model=ArticuloLeer)
def obtener_articulo(
    codigo: str,
    tenant: TenantContext = Depends(get_tenant),
) -> ArticuloLeer:
    articulo = service.obtener_articulo(tenant.session, tenant.org_id, codigo)
    if articulo is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Artículo no encontrado")
    return ArticuloLeer.model_validate(articulo)
