"""Endpoints de la ingesta visual: foto → propuesta → (humano) → escritura.

Son DOS endpoints y no uno, y esa es la feature: `/extraer` NO escribe nada, `/confirmar`
solo escribe lo que un humano aprobó. Un endpoint único "cargá este remito" sería más corto
y le daría a un modelo probabilístico permiso de escritura directa sobre stock y precios.

Orden de las rejas (igual que en el asistente): ban por IP → rate limit → validación de
tamaño y forma (Pydantic) → validación de la imagen → recién ahí el modelo.

Nota sobre el rate limit de `/extraer`: es el endpoint MÁS CARO del sistema (cada llamada
paga tokens de visión). Por eso 6/min y no 20: acá el límite protege la billetera, no solo
el CPU.
"""

import logging

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.exc import IntegrityError

from app.asistente import seguridad
from app.core.ratelimit import ip_cliente, limiter
from app.core.rls import TenantContext, get_tenant
from app.ingesta_visual import service
from app.ingesta_visual.extractor import ExtraccionFallida
from app.ingesta_visual.imagen import ImagenInvalida
from app.ingesta_visual.schemas import (
    ConfirmarRequest,
    ConfirmarResponse,
    ExtraerRequest,
    PropuestaResponse,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/ingesta-visual", tags=["ingesta-visual"])


@router.post("/extraer", response_model=PropuestaResponse)
@limiter.limit("6/minute")
def extraer(
    request: Request,
    body: ExtraerRequest,
    tenant: TenantContext = Depends(get_tenant),
) -> PropuestaResponse:
    """Lee la foto de un remito y devuelve una propuesta. NO ESCRIBE NADA.

    El texto que venga adentro de la imagen es DATO, no instrucción: los renglones que
    parezcan un intento de injection se marcan con el flag `texto_sospechoso` y llegan igual,
    para que el humano los vea. NO se banea al usuario por lo que dice el papel de su
    proveedor — eso sería castigarlo por un falso positivo.
    """
    if seguridad.esta_baneado(ip_cliente(request)):
        raise HTTPException(
            status.HTTP_429_TOO_MANY_REQUESTS, "Demasiados intentos. Probá más tarde."
        )

    try:
        return service.preparar_propuesta(
            tenant.session,
            tenant.org_id,
            imagen_base64=body.imagen_base64,
            mime=body.mime,
        )
    except ImagenInvalida as exc:
        # El único error que se le cuenta al cliente tal cual: es SU archivo y necesita saber
        # qué tiene de malo para poder arreglarlo.
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, str(exc)) from None
    except ExtraccionFallida:
        logger.exception("El modelo no devolvió un remito parseable")
        raise HTTPException(
            status.HTTP_502_BAD_GATEWAY,
            "Repu no pudo leer la foto. Probá con una imagen más nítida o más derecha.",
        ) from None
    except Exception:  # noqa: BLE001 — nunca filtrar internals (skill web-security)
        logger.exception("Error en /ingesta-visual/extraer")
        raise HTTPException(
            status.HTTP_500_INTERNAL_SERVER_ERROR, "No pude procesar la imagen."
        ) from None


@router.post("/confirmar", response_model=ConfirmarResponse)
@limiter.limit("20/minute")
def confirmar(
    request: Request,
    body: ConfirmarRequest,
    tenant: TenantContext = Depends(get_tenant),
) -> ConfirmarResponse:
    """Escribe el remito aprobado: artículos, stock, precios y proveedor. Todo o nada.

    NO confía en que el payload venga de `/extraer`: el servidor no recuerda la propuesta
    entre las dos llamadas, así que esto se valida como cualquier POST hostil (lo hace
    Pydantic) y se apoya en RLS.
    """
    if seguridad.esta_baneado(ip_cliente(request)):
        raise HTTPException(
            status.HTTP_429_TOO_MANY_REQUESTS, "Demasiados intentos. Probá más tarde."
        )

    try:
        return service.confirmar(
            tenant.session, tenant.org_id, datos=body, usuario_id=tenant.user_id
        )
    except service.DatoInvalido as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, str(exc)) from None
    except IntegrityError as exc:
        # El candado de idempotencia lo hace cumplir el motor, no un `if`. Acá aterrizan el
        # doble click y las dos pestañas confirmando a la vez.
        logger.info("Confirmación duplicada (org=%s): %s", tenant.org_id, exc)
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            "Este remito ya se cargó. Revisá el catálogo antes de volver a intentar.",
        ) from None
    except Exception:  # noqa: BLE001 — nunca filtrar internals (skill web-security)
        logger.exception("Error en /ingesta-visual/confirmar")
        raise HTTPException(
            status.HTTP_500_INTERNAL_SERVER_ERROR, "No pude cargar el remito."
        ) from None
