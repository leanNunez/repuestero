"""Endpoints de clientes: listar y dar de alta.

El alta genera el código en el servidor (`CLI-000001`) y valida CUIT y condición fiscal antes de
escribir. Los errores de negocio del service (`ValueError`) se traducen a 422; un choque de código
aterriza como 409 vía el unique. Nunca se filtran internals al cliente (skill web-security).
"""

import logging

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.exc import IntegrityError

from app.clientes import service
from app.clientes.schemas import ClienteCrear, ClienteLeer
from app.core.rls import TenantContext, get_tenant

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/clientes", tags=["clientes"])


@router.get("", response_model=list[ClienteLeer])
def listar(
    limite: int = Query(default=50, ge=1, le=200),
    tenant: TenantContext = Depends(get_tenant),
) -> list[ClienteLeer]:
    """Listado de los clientes activos de la org."""
    clientes = service.listar_clientes(tenant.session, tenant.org_id, limite=limite)
    return [ClienteLeer.model_validate(c) for c in clientes]


@router.post("", response_model=ClienteLeer, status_code=status.HTTP_201_CREATED)
def crear(
    body: ClienteCrear,
    tenant: TenantContext = Depends(get_tenant),
) -> ClienteLeer:
    """Da de alta un cliente. El código lo asigna el servidor, no viene en el body."""
    try:
        cliente = service.alta_cliente(
            tenant.session,
            tenant.org_id,
            denominacion=body.denominacion,
            cuit=body.cuit,
            cond_fiscal=body.cond_fiscal,
            limite_cta_cte=body.limite_cta_cte,
            telefono=body.telefono,
            email=body.email,
            direccion=body.direccion,
        )
    except ValueError as exc:
        # CUIT con dígito verificador malo o condición fiscal fuera del vocabulario.
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, str(exc)) from None
    except IntegrityError as exc:
        # Choque de `uq_clientes_org_codigo`. El unique es el árbitro, no un `if` previo: entre el
        # chequeo y el insert hay una ventana donde otra transacción mete el mismo código.
        logger.info("Alta de cliente en conflicto (org=%s): %s", tenant.org_id, exc)
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            "Ese código de cliente ya existe. Probá de nuevo.",
        ) from None
    except Exception:  # noqa: BLE001 — nunca filtrar internals (skill web-security)
        logger.exception("Error en POST /clientes")
        raise HTTPException(
            status.HTTP_500_INTERNAL_SERVER_ERROR,
            "No se pudo dar de alta el cliente.",
        ) from None

    return ClienteLeer.model_validate(cliente)
