"""Endpoints de caja: el extracto del libro, el saldo, y el alta manual.

Los errores de negocio del service (`CajaInvalida`) se traducen a 422. Nunca se filtran internals
al cliente (skill web-security).

NO hay endpoint para cargar un movimiento DERIVADO, y es la decisión central del módulo: esos los
escribe el service del documento que los genera (el recibo, la orden de pago), en su misma
transacción. Ver `app/core/conceptos_caja.py`.
"""

import logging
from collections.abc import Callable
from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.caja import service
from app.caja.schemas import (
    ChequeConciliarBody,
    ChequeLeer,
    ChequePagina,
    ChequeResponse,
    ChequeTransicionBody,
    EstadoChequeLiteral,
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


def _fecha(body: ChequeTransicionBody | None) -> date | None:
    """El body de una transición es opcional: sin él, la plata se mueve hoy."""
    return body.fecha if body is not None else None


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
        # Solo la forma que se acaba de tocar: un negativo viejo en otra forma no tiene nada que ver
        # con lo que la persona acaba de hacer, y avisarlo acá sería ruido.
        advertencias=service.advertencias_de_saldo(
            tenant.session, tenant.org_id, formas=[movimiento.forma]
        ),
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
    return SaldoCajaLeer(
        efectivo=por_forma["efectivo"],
        por_forma=por_forma,
        # De la tabla `cheques`, no del libro: son números distintos en cuanto hay cheques emitidos.
        cheques_en_cartera=service.valor_en_cartera(tenant.session, tenant.org_id),
    )


# ================================================================================ cartera


@router.get("/cheques", response_model=ChequePagina)
def listar_cheques(
    estado: EstadoChequeLiteral | None = Query(default=None),
    limite: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    tenant: TenantContext = Depends(get_tenant),
) -> ChequePagina:
    """La cartera, ordenada por fecha de cobro: los que se pueden depositar primero."""
    cheques, total = service.cartera(
        tenant.session, tenant.org_id, estado=estado, limite=limite, offset=offset
    )
    return ChequePagina(
        items=[ChequeLeer.model_validate(c) for c in cheques],
        total=total,
        valor_en_cartera=service.valor_en_cartera(tenant.session, tenant.org_id),
    )


def _transicion(
    operacion: Callable[..., service.Asiento],
    tenant: TenantContext,
    cheque_id: int,
    fecha: date | None,
    ruta: str,
) -> ChequeResponse:
    """El cuerpo compartido de las cuatro transiciones.

    Las cuatro hacen exactamente lo mismo salvo por qué función del service llaman, así que el
    manejo de errores y el armado de la respuesta se escriben una vez. Repetirlo cuatro veces
    garantizaría que dentro de un mes tres estén actualizadas y una no.

    Los tres desenlaces son distintos a propósito: 404 si el cheque no existe, 422 si existe pero
    la transición no es válida, 500 sin filtrar internals para cualquier otra cosa.
    """
    try:
        asiento = operacion(
            tenant.session,
            tenant.org_id,
            cheque_id,
            fecha=fecha,
            usuario_id=tenant.user_id,
        )
    except service.ChequeNoEncontrado as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, str(exc)) from None
    except service.CajaInvalida as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, str(exc)) from None
    except Exception:  # noqa: BLE001 — nunca filtrar internals (skill web-security)
        logger.exception("Error en POST /caja/cheques/{id}/%s", ruta)
        raise HTTPException(
            status.HTTP_500_INTERNAL_SERVER_ERROR, "No pude registrar la operación."
        ) from None

    saldos = service.saldo_por_forma(tenant.session, tenant.org_id)
    return ChequeResponse(
        cheque=ChequeLeer.model_validate(asiento.cheques[0]),
        movimientos=[
            MovimientoCajaResponse(
                movimiento_id=m.id, concepto=m.concepto, forma=m.forma, saldo=saldos[m.forma]
            )
            for m in asiento.movimientos
        ],
        saldos=saldos,
    )


@router.post("/cheques/{cheque_id}/depositar", response_model=ChequeResponse)
def depositar(
    cheque_id: int,
    tenant: TenantContext = Depends(get_tenant),
) -> ChequeResponse:
    """Al banco. No mueve plata, así que `movimientos` vuelve vacío."""
    return _transicion(service.depositar, tenant, cheque_id, None, "depositar")


@router.post("/cheques/{cheque_id}/cobrar", response_model=ChequeResponse)
def cobrar(
    cheque_id: int,
    body: ChequeTransicionBody | None = None,
    tenant: TenantContext = Depends(get_tenant),
) -> ChequeResponse:
    """Se hizo efectivo. Acredita en `efectivo` si estaba en cartera (ventanilla) o en
    `transferencia` si estaba depositado (lo acreditó el banco)."""
    return _transicion(service.cobrar, tenant, cheque_id, _fecha(body), "cobrar")


@router.post("/cheques/{cheque_id}/rechazar", response_model=ChequeResponse)
def rechazar(
    cheque_id: int,
    body: ChequeTransicionBody | None = None,
    tenant: TenantContext = Depends(get_tenant),
) -> ChequeResponse:
    """Volvió del banco. Sale de la cartera sin acreditar nada."""
    return _transicion(service.rechazar, tenant, cheque_id, _fecha(body), "rechazar")


@router.post("/cheques/{cheque_id}/entregar", response_model=ChequeResponse)
def entregar(
    cheque_id: int,
    body: ChequeTransicionBody | None = None,
    tenant: TenantContext = Depends(get_tenant),
) -> ChequeResponse:
    """Endosado a un proveedor."""
    return _transicion(service.entregar, tenant, cheque_id, _fecha(body), "entregar")


@router.post("/cheques/{cheque_id}/conciliar", response_model=ChequeLeer)
def conciliar(
    cheque_id: int,
    body: ChequeConciliarBody,
    tenant: TenantContext = Depends(get_tenant),
) -> ChequeLeer:
    """Contra el resumen bancario. No pasa por la máquina de estados: conciliar es ortogonal al
    estado del papel, y la fecha es obligatoria porque sin ella no se puede auditar."""
    try:
        cheque = service.conciliar(tenant.session, tenant.org_id, cheque_id, fecha=body.fecha)
    except service.ChequeNoEncontrado as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, str(exc)) from None
    except service.CajaInvalida as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, str(exc)) from None
    except Exception:  # noqa: BLE001 — nunca filtrar internals (skill web-security)
        logger.exception("Error en POST /caja/cheques/{id}/conciliar")
        raise HTTPException(
            status.HTTP_500_INTERNAL_SERVER_ERROR, "No pude conciliar el cheque."
        ) from None

    return ChequeLeer.model_validate(cheque)
