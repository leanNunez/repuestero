"""Endpoints de ventas: emitir comprobante, listarlos, ver el detalle.

El POST escribe (cabecera + renglones + stock) en UNA transacción. Los errores de negocio del
service (`VentaInvalida`) se traducen a 422; el choque de numeración concurrente aterriza como
409 vía el unique del comprobante. Nunca se filtran internals al cliente (skill web-security).
"""

import logging

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.exc import IntegrityError

from app.clientes import service as clientes
from app.core.rls import TenantContext, get_tenant
from app.ventas import service
from app.ventas.schemas import (
    CobranzaCrear,
    CobranzaResponse,
    CuentaLeer,
    CuentaPagina,
    MovimientoLeer,
    MovimientoPagina,
    NotaCreditoCrear,
    NotaCreditoDetalle,
    NotaCreditoItemLeer,
    NotaCreditoLeer,
    NotaCreditoPagina,
    NotaCreditoResponse,
    PrecioSugeridoLeer,
    RenglonAcreditableLeer,
    SaldoLeer,
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


@router.get("/precio-sugerido", response_model=PrecioSugeridoLeer)
def precio_sugerido(
    articulo_codigo: str = Query(min_length=1, max_length=40),
    cliente_codigo: str | None = Query(default=None, max_length=20),
    tenant: TenantContext = Depends(get_tenant),
) -> PrecioSugeridoLeer:
    """Precio a precargar en un renglón: el de la lista del cliente, o Mostrador. Sugerencia
    editable — la venta usa el precio del payload, no este."""
    sugerido = service.precio_sugerido(
        tenant.session,
        tenant.org_id,
        articulo_codigo=articulo_codigo,
        cliente_codigo=cliente_codigo,
    )
    if sugerido is None:
        return PrecioSugeridoLeer(articulo_codigo=articulo_codigo)
    precio, lista_codigo = sugerido
    return PrecioSugeridoLeer(
        articulo_codigo=articulo_codigo, precio=precio, lista_codigo=lista_codigo
    )


# --- Notas de crédito. Las rutas literales van ANTES de `/{venta_id}`: si no, el conversor int
# --- de venta_id rechaza "notas-credito" con un 422 en vez de dejar pasar a estas.


@router.post(
    "/notas-credito", response_model=NotaCreditoResponse, status_code=status.HTTP_201_CREATED
)
def crear_nota_credito(
    body: NotaCreditoCrear,
    tenant: TenantContext = Depends(get_tenant),
) -> NotaCreditoResponse:
    try:
        nota = service.crear_nota_credito(
            tenant.session, tenant.org_id, datos=body, usuario_id=tenant.user_id
        )
    except service.NotaCreditoInvalida as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, str(exc)) from None
    except IntegrityError as exc:
        # Choque de numeración concurrente: el unique de la NC es el árbitro, no un `if`.
        logger.info("NC duplicada/colisión de numeración (org=%s): %s", tenant.org_id, exc)
        raise HTTPException(
            status.HTTP_409_CONFLICT, "No se pudo asignar el número. Reintentá."
        ) from None
    except Exception:  # noqa: BLE001 — nunca filtrar internals (skill web-security)
        logger.exception("Error en POST /ventas/notas-credito")
        raise HTTPException(
            status.HTTP_500_INTERNAL_SERVER_ERROR, "No pude registrar la nota de crédito."
        ) from None

    items = service.items_de_nota_credito(tenant.session, tenant.org_id, nota.id)
    return NotaCreditoResponse(
        nota_credito_id=nota.id,
        ref_comprobante_id=nota.ref_comprobante_id,
        tipo=nota.tipo,
        pto_venta=nota.pto_venta,
        numero=nota.numero,
        total=nota.total,
        movimientos=len(items),
    )


@router.get("/notas-credito", response_model=NotaCreditoPagina)
def listar_notas_credito(
    limite: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    tenant: TenantContext = Depends(get_tenant),
) -> NotaCreditoPagina:
    notas, total = service.listar_notas_credito(
        tenant.session, tenant.org_id, limite=limite, offset=offset
    )
    return NotaCreditoPagina(items=[NotaCreditoLeer.model_validate(n) for n in notas], total=total)


@router.get("/notas-credito/{nc_id}", response_model=NotaCreditoDetalle)
def obtener_nota_credito(
    nc_id: int,
    tenant: TenantContext = Depends(get_tenant),
) -> NotaCreditoDetalle:
    nota = service.obtener_nota_credito(tenant.session, tenant.org_id, nc_id)
    if nota is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "No existe esa nota de crédito.")
    items = service.items_de_nota_credito(tenant.session, tenant.org_id, nc_id)
    return NotaCreditoDetalle(
        **NotaCreditoLeer.model_validate(nota).model_dump(),
        items=[NotaCreditoItemLeer.model_validate(i) for i in items],
    )


# --- Cuenta corriente. `/cuenta-corriente` es UN solo segmento, así que la captura
# --- `/{venta_id}` de más abajo: va declarada antes, por el mismo motivo que las de NC.


@router.get("/cuenta-corriente", response_model=CuentaPagina)
def listar_cuenta_corriente(
    buscar: str | None = Query(default=None, max_length=80),
    solo_con_saldo: bool = Query(default=True),
    limite: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    tenant: TenantContext = Depends(get_tenant),
) -> CuentaPagina:
    cuentas, total, saldo_total = service.listar_cuentas_clientes(
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


@router.get("/clientes/{cliente_id}/movimientos", response_model=MovimientoPagina)
def listar_movimientos_cliente(
    cliente_id: int,
    limite: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    tenant: TenantContext = Depends(get_tenant),
) -> MovimientoPagina:
    cliente = clientes.obtener_cliente_por_id(tenant.session, tenant.org_id, cliente_id)
    if cliente is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "No existe ese cliente.")

    movimientos, total = service.movimientos_cliente(
        tenant.session, tenant.org_id, cliente_id, limite=limite, offset=offset
    )
    return MovimientoPagina(
        items=[MovimientoLeer(**m._asdict()) for m in movimientos],
        total=total,
        cuenta=CuentaLeer(
            id=cliente.id,
            codigo=cliente.codigo,
            nombre=cliente.denominacion,
            saldo=service.saldo_cliente(tenant.session, tenant.org_id, cliente_id),
            limite=cliente.limite_cta_cte,
        ),
    )


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


@router.get("/{venta_id}/acreditable", response_model=list[RenglonAcreditableLeer])
def renglones_acreditables(
    venta_id: int,
    tenant: TenantContext = Depends(get_tenant),
) -> list[RenglonAcreditableLeer]:
    """Lo que resta acreditar de cada renglón de una venta — la UI lo usa para fijar los máximos
    del flujo de NC. Una venta inexistente devuelve lista vacía (no hay nada para acreditar)."""
    if service.obtener_venta(tenant.session, tenant.org_id, venta_id) is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "No existe esa venta.")
    renglones = service.renglones_acreditables(tenant.session, tenant.org_id, venta_id)
    return [RenglonAcreditableLeer(**r._asdict()) for r in renglones]


@router.post("/cobranzas", response_model=CobranzaResponse, status_code=status.HTTP_201_CREATED)
def registrar_cobranza(
    body: CobranzaCrear,
    tenant: TenantContext = Depends(get_tenant),
) -> CobranzaResponse:
    try:
        movimiento = service.registrar_cobranza(
            tenant.session,
            tenant.org_id,
            cliente_codigo=body.cliente_codigo,
            monto=body.monto,
            usuario_id=tenant.user_id,
        )
    except service.VentaInvalida as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, str(exc)) from None
    except Exception:  # noqa: BLE001 — nunca filtrar internals (skill web-security)
        logger.exception("Error en POST /ventas/cobranzas")
        raise HTTPException(
            status.HTTP_500_INTERNAL_SERVER_ERROR, "No pude registrar la cobranza."
        ) from None

    return CobranzaResponse(
        movimiento_id=movimiento.id,
        cliente_id=movimiento.cliente_id,
        saldo=service.saldo_cliente(tenant.session, tenant.org_id, movimiento.cliente_id),
    )


@router.get("/clientes/{cliente_id}/saldo", response_model=SaldoLeer)
def saldo_cliente(
    cliente_id: int,
    tenant: TenantContext = Depends(get_tenant),
) -> SaldoLeer:
    return SaldoLeer(
        cliente_id=cliente_id,
        saldo=service.saldo_cliente(tenant.session, tenant.org_id, cliente_id),
    )
