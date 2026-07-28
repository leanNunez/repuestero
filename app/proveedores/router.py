"""Endpoints de proveedores: listar y dar de alta.

El alta genera el código en el servidor (`PRV-000001`) y valida el CUIT antes de escribir. Los
errores de negocio del service (`ValueError`) se traducen a 422; un choque de código aterriza como
409 vía el unique. Nunca se filtran internals al cliente (skill web-security).
"""

import logging

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.exc import IntegrityError

from app.core.rls import TenantContext, get_tenant
from app.proveedores import service
from app.proveedores.schemas import ProveedorCrear, ProveedorLeer, ProveedorPagina

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/proveedores", tags=["proveedores"])


@router.get("", response_model=ProveedorPagina)
def listar(
    buscar: str | None = Query(default=None, max_length=80),
    limite: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    tenant: TenantContext = Depends(get_tenant),
) -> ProveedorPagina:
    """Página del padrón de proveedores activos de la org, con búsqueda opcional.

    Devuelve `{items, total}` y no un array: sin el total no hay paginación posible del otro lado.
    """
    proveedores, total = service.listar_proveedores(
        tenant.session,
        tenant.org_id,
        buscar=buscar,
        limite=limite,
        offset=offset,
    )
    return ProveedorPagina(
        items=[ProveedorLeer.model_validate(p) for p in proveedores], total=total
    )


@router.post("", response_model=ProveedorLeer, status_code=status.HTTP_201_CREATED)
def crear(
    body: ProveedorCrear,
    tenant: TenantContext = Depends(get_tenant),
) -> ProveedorLeer:
    """Da de alta un proveedor. El código lo asigna el servidor, no viene en el body."""
    try:
        proveedor = service.alta_proveedor(
            tenant.session,
            tenant.org_id,
            razon_social=body.razon_social,
            cuit=body.cuit,
            telefono=body.telefono,
            email=body.email,
        )
    except ValueError as exc:
        # CUIT con dígito verificador malo.
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, str(exc)) from None
    except IntegrityError as exc:
        # Choque de `uq_proveedores_org_codigo`. El unique es el árbitro, no un `if` previo: entre
        # el chequeo y el insert hay una ventana donde otra transacción mete el mismo código.
        logger.info("Alta de proveedor en conflicto (org=%s): %s", tenant.org_id, exc)
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            "Ese código de proveedor ya existe. Probá de nuevo.",
        ) from None
    except Exception:  # noqa: BLE001 — nunca filtrar internals (skill web-security)
        logger.exception("Error en POST /proveedores")
        raise HTTPException(
            status.HTTP_500_INTERNAL_SERVER_ERROR,
            "No se pudo dar de alta el proveedor.",
        ) from None

    return ProveedorLeer.model_validate(proveedor)
