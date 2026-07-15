"""Endpoint del asistente conversacional. La primera línea de defensa vive acá.

Orden de las rejas: ban por IP → rate limit → validación de tamaño (Pydantic) → filtro anti
injection → recién ahí el grafo NL2SQL (que suma el rol read-only y el guard de SQL). Un ataque
se frena lo antes posible, antes de gastar un token de LLM.
"""

import logging

from fastapi import APIRouter, Depends, HTTPException, Request, status

from app.asistente import seguridad, service
from app.asistente.schemas import ConsultaRequest, ConsultaResponse
from app.core.ratelimit import limiter
from app.core.rls import TenantContext, get_tenant

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/asistente", tags=["asistente"])

# Solo se confía en X-Forwarded-For si viene de un proxy conocido (spoofeable si no).
_PROXIES_CONFIABLES = {"127.0.0.1", "::1"}


def _ip(request: Request) -> str:
    ip = request.client.host if request.client else "unknown"
    if ip in _PROXIES_CONFIABLES:
        fwd = request.headers.get("x-forwarded-for", "")
        if fwd:
            return fwd.split(",")[0].strip()
    return ip


@router.post("/consultar", response_model=ConsultaResponse)
@limiter.limit("20/minute")
def consultar(
    request: Request,
    body: ConsultaRequest,
    tenant: TenantContext = Depends(get_tenant),
) -> ConsultaResponse:
    ip = _ip(request)

    if seguridad.esta_baneado(ip):
        raise HTTPException(status.HTTP_429_TOO_MANY_REQUESTS, "Demasiados intentos. Probá más tarde.")

    if seguridad.es_injection(body.message):
        seguridad.registrar_intento(ip)
        return ConsultaResponse(
            answer="No puedo procesar esa consulta. Preguntame sobre tu catálogo, stock o clientes.",
            blocked=True,
        )

    try:
        resultado = service.consultar(tenant, body.message)
    except Exception:  # noqa: BLE001 — nunca filtrar internals al cliente (skill web-security)
        logger.exception("Error en /asistente/consultar")
        raise HTTPException(
            status.HTTP_500_INTERNAL_SERVER_ERROR, "No pude procesar la consulta."
        ) from None

    return ConsultaResponse(
        answer=resultado["respuesta"] or "",
        sql=resultado["sql"],
        filas=resultado["filas"],
    )
