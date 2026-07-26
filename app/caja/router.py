"""Endpoints de caja: el extracto del libro, el saldo, y el alta manual.

Los errores de negocio del service (`CajaInvalida`) se traducen a 422. Nunca se filtran internals
al cliente (skill web-security).

NO hay endpoint para cargar un movimiento DERIVADO, y es la decisión central del módulo: esos los
escribe el service del documento que los genera (el recibo, la orden de pago), en su misma
transacción. Ver `app/core/conceptos_caja.py`.
"""

import logging

from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.caja import service
from app.caja.schemas import (
    MovimientoCajaCrear,
    MovimientoCajaLeer,
    MovimientoCajaPagina,
    MovimientoCajaResponse,
    SaldoCajaLeer,
)
from app.core.formas_pago import FormaPagoLiteral
from app.core.rls import TenantContext, get_tenant

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/caja", tags=["caja"])


@router.post(
    "/movimientos", response_model=MovimientoCajaResponse, status_code=status.HTTP_201_CREATED
)
def registrar_movimiento(
    body: MovimientoCajaCrear,
    tenant: TenantContext = Depends(get_tenant),
) -> MovimientoCajaResponse:
    """Carga a mano un gasto, un retiro o un aporte. Los conceptos derivados los rechaza el
    schema con un 422 antes de llegar acá."""
    try:
        movimiento = service.registrar_movimiento(
            tenant.session,
            tenant.org_id,
            concepto=body.concepto,
            forma=body.forma,
            monto=body.monto,
            detalle=body.detalle,
            fecha=body.fecha,
            usuario_id=tenant.user_id,
        )
    except service.CajaInvalida as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, str(exc)) from None
    except Exception:  # noqa: BLE001 — nunca filtrar internals (skill web-security)
        logger.exception("Error en POST /caja/movimientos")
        raise HTTPException(
            status.HTTP_500_INTERNAL_SERVER_ERROR, "No pude registrar el movimiento."
        ) from None

    return MovimientoCajaResponse(
        movimiento_id=movimiento.id,
        concepto=movimiento.concepto,
        forma=movimiento.forma,
        saldo=service.saldo_por_forma(tenant.session, tenant.org_id)[movimiento.forma],
    )


@router.get("/movimientos", response_model=MovimientoCajaPagina)
def listar_movimientos(
    forma: FormaPagoLiteral | None = Query(default=None),
    limite: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    tenant: TenantContext = Depends(get_tenant),
) -> MovimientoCajaPagina:
    """Extracto del libro. Sin `forma` trae todo; con `forma` trae el de esa forma, y en los dos
    casos el `saldo_acumulado` de cada fila es el de SU forma (ver `service.movimientos`)."""
    movimientos, total = service.movimientos(
        tenant.session, tenant.org_id, forma=forma, limite=limite, offset=offset
    )
    return MovimientoCajaPagina(
        items=[MovimientoCajaLeer(**m._asdict()) for m in movimientos], total=total
    )


@router.get("/saldo", response_model=SaldoCajaLeer)
def saldo(tenant: TenantContext = Depends(get_tenant)) -> SaldoCajaLeer:
    por_forma = service.saldo_por_forma(tenant.session, tenant.org_id)
    return SaldoCajaLeer(efectivo=por_forma["efectivo"], por_forma=por_forma)
