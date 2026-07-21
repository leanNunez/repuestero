"""Endpoints de ventas: emitir comprobante, listarlos, ver el detalle.

El POST escribe (cabecera + renglones + stock) en UNA transacción. Los errores de negocio del
service (`VentaInvalida`) se traducen a 422; el choque de numeración concurrente aterriza como
409 vía el unique del comprobante. Nunca se filtran internals al cliente (skill web-security).
"""

import logging

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.exc import IntegrityError

from app.core.rls import TenantContext, get_tenant
from app.ventas import service
from app.ventas.schemas import (
    VentaCrear,
    VentaDetalle,
    VentaItemLeer,
    VentaLeer,
    VentaPagina,
    VentaResponse,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/ventas", tags=["ventas"])


@router.post("", response_model=VentaResponse, status_code=status.HTTP_201_CREATED)
def crear_venta(
    body: VentaCrear,
    tenant: TenantContext = Depends(get_tenant),
) -> VentaResponse:
    try:
        comprobante = service.crear_venta(
            tenant.session, tenant.org_id, datos=body, usuario_id=tenant.user_id
        )
    except service.VentaInvalida as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, str(exc)) from None
    except IntegrityError as exc:
        # Choque de numeración concurrente: el unique del comprobante es el árbitro, no un `if`.
        logger.info("Venta duplicada/colisión de numeración (org=%s): %s", tenant.org_id, exc)
        raise HTTPException(
            status.HTTP_409_CONFLICT, "No se pudo asignar el número. Reintentá."
        ) from None
    except Exception:  # noqa: BLE001 — nunca filtrar internals (skill web-security)
        logger.exception("Error en POST /ventas")
        raise HTTPException(
            status.HTTP_500_INTERNAL_SERVER_ERROR, "No pude registrar la venta."
        ) from None

    return VentaResponse(
        venta_id=comprobante.id,
        tipo=comprobante.tipo,
        pto_venta=comprobante.pto_venta,
        numero=comprobante.numero,
        total=comprobante.total,
        movimientos=len(body.renglones),
    )


@router.get("", response_model=VentaPagina)
def listar_ventas(
    limite: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    tenant: TenantContext = Depends(get_tenant),
) -> VentaPagina:
    ventas, total = service.listar_ventas(
        tenant.session, tenant.org_id, limite=limite, offset=offset
    )
    return VentaPagina(items=[VentaLeer.model_validate(v) for v in ventas], total=total)


@router.get("/{venta_id}", response_model=VentaDetalle)
def obtener_venta(
    venta_id: int,
    tenant: TenantContext = Depends(get_tenant),
) -> VentaDetalle:
    comprobante = service.obtener_venta(tenant.session, tenant.org_id, venta_id)
    if comprobante is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "No existe esa venta.")
    items = service.items_de_venta(tenant.session, tenant.org_id, venta_id)
    return VentaDetalle(
        **VentaLeer.model_validate(comprobante).model_dump(),
        items=[VentaItemLeer.model_validate(i) for i in items],
    )
