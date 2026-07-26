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
    AjusteCrear,
    AjusteResponse,
    CompraCrear,
    CompraDetalle,
    CompraItemLeer,
    CompraLeer,
    CompraPagina,
    CompraResponse,
    CuentaLeer,
    CuentaPagina,
    FormaPagoLeer,
    MovimientoLeer,
    MovimientoPagina,
    OrdenPagoLeer,
    PagoProveedorCrear,
    PagoProveedorResponse,
    SaldoProveedorLeer,
)
from app.core.rls import TenantContext, get_tenant
from app.proveedores import service as proveedores

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
    """Paga al proveedor EMITIENDO UNA ORDEN DE PAGO, y la imputa como Haber.

    `formas_pago` puede omitirse: el schema asume el total en efectivo. La orden, en cambio, se
    emite siempre — no hay pago sin documento.
    """
    formas = [service.FormaPago(forma=f.forma, monto=f.monto) for f in body.formas_pago or []]
    try:
        pago = service.registrar_pago(
            tenant.session,
            tenant.org_id,
            proveedor_codigo=body.proveedor_codigo,
            monto=body.monto,
            formas_pago=formas,
            fecha=body.fecha,
            pto_venta=body.pto_venta,
            usuario_id=tenant.user_id,
        )
    except service.CompraInvalida as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, str(exc)) from None
    except IntegrityError:
        # El unique de la orden atajó una colisión de numeración. Mismo 409 que la compra.
        raise HTTPException(
            status.HTTP_409_CONFLICT, "No pude asignar el número de orden de pago. Reintentá."
        ) from None
    except Exception:  # noqa: BLE001 — nunca filtrar internals (skill web-security)
        logger.exception("Error en POST /compras/pagos")
        raise HTTPException(
            status.HTTP_500_INTERNAL_SERVER_ERROR, "No pude registrar el pago."
        ) from None

    movimiento, orden = pago.movimiento, pago.orden
    return PagoProveedorResponse(
        movimiento_id=movimiento.id,
        proveedor_id=movimiento.proveedor_id,
        saldo=service.saldo_proveedor(tenant.session, tenant.org_id, movimiento.proveedor_id),
        documento_id=orden.id,
        documento_tipo=orden.tipo,
        documento_pto_venta=orden.pto_venta,
        documento_numero=orden.numero,
    )


@router.post(
    "/proveedores/{proveedor_id}/ajustes",
    response_model=AjusteResponse,
    status_code=status.HTTP_201_CREATED,
)
def registrar_ajuste(
    proveedor_id: int,
    body: AjusteCrear,
    tenant: TenantContext = Depends(get_tenant),
) -> AjusteResponse:
    """Corrige la cuenta corriente del proveedor: reversa de un movimiento, o ajuste a mano.

    Espejo de `POST /ventas/clientes/{id}/ajustes`. Ver `service.registrar_ajuste`.
    """
    # El proveedor viaja en el PATH, así que su ausencia es un 404 — igual que en el GET de
    # movimientos. `/pagos` devuelve 422 porque ahí el proveedor va en el body.
    if proveedores.obtener_proveedor_por_id(tenant.session, tenant.org_id, proveedor_id) is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "No existe ese proveedor.")

    try:
        movimiento = service.registrar_ajuste(
            tenant.session,
            tenant.org_id,
            proveedor_id=proveedor_id,
            motivo=body.motivo,
            debe=body.debe,
            haber=body.haber,
            revierte_movimiento_id=body.revierte_movimiento_id,
            fecha=body.fecha,
            usuario_id=tenant.user_id,
        )
    except service.CompraInvalida as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, str(exc)) from None
    except IntegrityError:
        # El índice único parcial de la 0009 atajó una doble reversa simultánea: el chequeo del
        # service pasó y otra transacción se metió en el medio.
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY, "Ese movimiento ya fue revertido con un ajuste."
        ) from None
    except Exception:  # noqa: BLE001 — nunca filtrar internals (skill web-security)
        logger.exception("Error en POST /compras/proveedores/%s/ajustes", proveedor_id)
        raise HTTPException(
            status.HTTP_500_INTERNAL_SERVER_ERROR, "No pude registrar el ajuste."
        ) from None

    return AjusteResponse(
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


# --- Cuenta corriente. `/cuenta-corriente` es UN solo segmento, así que la captura
# --- `/{compra_id}` de más abajo: va declarada antes.


@router.get("/cuenta-corriente", response_model=CuentaPagina)
def listar_cuenta_corriente(
    buscar: str | None = Query(default=None, max_length=80),
    solo_con_saldo: bool = Query(default=True),
    limite: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    tenant: TenantContext = Depends(get_tenant),
) -> CuentaPagina:
    cuentas, total, saldo_total = service.listar_cuentas_proveedores(
        tenant.session,
        tenant.org_id,
        buscar=buscar,
        solo_con_saldo=solo_con_saldo,
        limite=limite,
        offset=offset,
    )
    return CuentaPagina(
        items=[CuentaLeer(**c._asdict()) for c in cuentas],
        total=total,
        saldo_total=saldo_total,
    )


@router.get("/proveedores/{proveedor_id}/movimientos", response_model=MovimientoPagina)
def listar_movimientos_proveedor(
    proveedor_id: int,
    limite: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    tenant: TenantContext = Depends(get_tenant),
) -> MovimientoPagina:
    proveedor = proveedores.obtener_proveedor_por_id(tenant.session, tenant.org_id, proveedor_id)
    if proveedor is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "No existe ese proveedor.")

    movimientos, total = service.movimientos_proveedor(
        tenant.session, tenant.org_id, proveedor_id, limite=limite, offset=offset
    )
    return MovimientoPagina(
        items=[MovimientoLeer(**m._asdict()) for m in movimientos],
        total=total,
        cuenta=CuentaLeer(
            id=proveedor.id,
            codigo=proveedor.codigo,
            nombre=proveedor.razon_social,
            saldo=service.saldo_proveedor(tenant.session, tenant.org_id, proveedor_id),
        ),
    )


@router.get("/ordenes-pago/{orden_id}", response_model=OrdenPagoLeer)
def obtener_orden_pago(
    orden_id: int,
    tenant: TenantContext = Depends(get_tenant),
) -> OrdenPagoLeer:
    """La orden de pago de un pago, con su detalle de formas.

    Va ANTES de `/{compra_id}` a propósito: FastAPI resuelve por orden de declaración, y si esta
    ruta quedara después, `/compras/ordenes-pago/12` entraría por la genérica y `ordenes-pago`
    explotaría al convertirse a int. Espejo de `/ventas/recibos/{id}`.
    """
    orden = service.obtener_orden_pago(tenant.session, tenant.org_id, orden_id)
    if orden is None:
        # El RLS ya filtró por org: una orden de otra organización llega acá como None. 404, no
        # 403 — no se le confirma a nadie que ese id existe en otro tenant.
        raise HTTPException(status.HTTP_404_NOT_FOUND, "No existe esa orden de pago.")

    formas = service.formas_de_orden_pago(tenant.session, tenant.org_id, orden_id)
    return OrdenPagoLeer(
        **OrdenPagoLeer.model_validate(orden).model_dump(exclude={"formas_pago"}),
        formas_pago=[FormaPagoLeer.model_validate(f) for f in formas],
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
