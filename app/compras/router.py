"""Endpoints de compras: registrar una compra, listarlas, ver el detalle, pagar al proveedor.

El POST escribe (cabecera + renglones + stock + costos) en UNA transacción. Los errores de negocio
del service (`CompraInvalida`) se traducen a 422; cargar dos veces la misma factura del proveedor
aterriza como 409 vía el unique. Nunca se filtran internals al cliente (skill web-security).
"""

import logging

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.exc import IntegrityError

from app.compras import service
from app.compras.schemas import (
    CompraCrear,
    CompraDetalle,
    CompraItemLeer,
    CompraLeer,
    CompraPagina,
    CompraResponse,
    PagoProveedorCrear,
    PagoProveedorResponse,
    SaldoProveedorLeer,
)
from app.core.rls import TenantContext, get_tenant

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/compras", tags=["compras"])


@router.post("", response_model=CompraResponse, status_code=status.HTTP_201_CREATED)
def crear_compra(
    body: CompraCrear,
    tenant: TenantContext = Depends(get_tenant),
) -> CompraResponse:
    try:
        compra = service.crear_compra(
            tenant.session, tenant.org_id, datos=body, usuario_id=tenant.user_id
        )
    except service.CompraInvalida as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, str(exc)) from None
    except IntegrityError as exc:
        # Factura del proveedor ya cargada: el unique de la compra es el árbitro, no un `if`.
        logger.info("Compra duplicada (org=%s): %s", tenant.org_id, exc)
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            "Esa factura del proveedor ya está cargada.",
        ) from None
    except Exception:  # noqa: BLE001 — nunca filtrar internals (skill web-security)
        logger.exception("Error en POST /compras")
        raise HTTPException(
            status.HTTP_500_INTERNAL_SERVER_ERROR, "No pude registrar la compra."
        ) from None

    return CompraResponse(
        compra_id=compra.id,
        proveedor_id=compra.proveedor_id,
        numero_comprobante=compra.numero_comprobante,
        total=compra.total,
        movimientos=len(body.renglones),
    )


@router.get("", response_model=CompraPagina)
def listar_compras(
    limite: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    tenant: TenantContext = Depends(get_tenant),
) -> CompraPagina:
    compras, total = service.listar_compras(
        tenant.session, tenant.org_id, limite=limite, offset=offset
    )
    return CompraPagina(items=[CompraLeer.model_validate(c) for c in compras], total=total)


@router.post("/pagos", response_model=PagoProveedorResponse, status_code=status.HTTP_201_CREATED)
def registrar_pago(
    body: PagoProveedorCrear,
    tenant: TenantContext = Depends(get_tenant),
) -> PagoProveedorResponse:
    try:
        movimiento = service.registrar_pago(
            tenant.session,
            tenant.org_id,
            proveedor_codigo=body.proveedor_codigo,
            monto=body.monto,
            usuario_id=tenant.user_id,
        )
    except service.CompraInvalida as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, str(exc)) from None
    except Exception:  # noqa: BLE001 — nunca filtrar internals (skill web-security)
        logger.exception("Error en POST /compras/pagos")
        raise HTTPException(
            status.HTTP_500_INTERNAL_SERVER_ERROR, "No pude registrar el pago."
        ) from None

    return PagoProveedorResponse(
        movimiento_id=movimiento.id,
        proveedor_id=movimiento.proveedor_id,
        saldo=service.saldo_proveedor(tenant.session, tenant.org_id, movimiento.proveedor_id),
    )


@router.get("/proveedores/{proveedor_id}/saldo", response_model=SaldoProveedorLeer)
def saldo_proveedor(
    proveedor_id: int,
    tenant: TenantContext = Depends(get_tenant),
) -> SaldoProveedorLeer:
    return SaldoProveedorLeer(
        proveedor_id=proveedor_id,
        saldo=service.saldo_proveedor(tenant.session, tenant.org_id, proveedor_id),
    )


@router.get("/{compra_id}", response_model=CompraDetalle)
def obtener_compra(
    compra_id: int,
    tenant: TenantContext = Depends(get_tenant),
) -> CompraDetalle:
    compra = service.obtener_compra(tenant.session, tenant.org_id, compra_id)
    if compra is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "No existe esa compra.")
    items = service.items_de_compra(tenant.session, tenant.org_id, compra_id)
    return CompraDetalle(
        **CompraLeer.model_validate(compra).model_dump(),
        items=[CompraItemLeer.model_validate(i) for i in items],
    )
