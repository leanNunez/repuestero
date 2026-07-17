"""Endpoint del asistente conversacional. La primera línea de defensa vive acá.

Orden de las rejas: ban por IP → rate limit → validación de tamaño (Pydantic) → filtro anti
injection → recién ahí el grafo NL2SQL (que suma el rol read-only y el guard de SQL). Un ataque
se frena lo antes posible, antes de gastar un token de LLM.
"""

import json
import logging
from collections.abc import Iterator

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sse_starlette.sse import EventSourceResponse, ServerSentEvent

from app.asistente import seguridad, service
from app.asistente.schemas import ConsultaRequest, ConsultaResponse
from app.core.ratelimit import ip_cliente, limiter
from app.core.rls import TenantContext, get_tenant

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/asistente", tags=["asistente"])

# Respuesta única cuando se detecta prompt injection. La comparten /consultar y /stream.
_MSG_BLOQUEADO = "No puedo procesar esa consulta. Preguntame sobre tu catálogo, stock o clientes."


@router.post("/consultar", response_model=ConsultaResponse)
@limiter.limit("20/minute")
def consultar(
    request: Request,
    body: ConsultaRequest,
    tenant: TenantContext = Depends(get_tenant),
) -> ConsultaResponse:
    ip = ip_cliente(request)

    if seguridad.esta_baneado(ip):
        raise HTTPException(
            status.HTTP_429_TOO_MANY_REQUESTS, "Demasiados intentos. Probá más tarde."
        )

    if seguridad.es_injection(body.message):
        seguridad.registrar_intento(ip)
        return ConsultaResponse(answer=_MSG_BLOQUEADO, blocked=True)

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


def _sse(event: str, **data) -> ServerSentEvent:
    return ServerSentEvent(event=event, data=json.dumps(data, ensure_ascii=False))


def _stream_bloqueado() -> Iterator[ServerSentEvent]:
    yield _sse("bloqueado", answer=_MSG_BLOQUEADO)
    yield _sse("fin")


def _stream_seguro(tenant: TenantContext, mensaje: str) -> Iterator[ServerSentEvent]:
    """Envuelve el stream del servicio: una excepción a mitad de camino no debe filtrar internals ni
    cortar el SSE en seco — se emite un `error` genérico y se cierra limpio."""
    try:
        yield from service.consultar_stream(tenant, mensaje)
    except Exception:  # noqa: BLE001 — nunca filtrar internals al cliente (skill web-security)
        logger.exception("Error en /asistente/stream")
        yield _sse("error", mensaje="No pude procesar la consulta.")
        yield _sse("fin")


@router.post("/stream")
@limiter.limit("20/minute")
def stream(
    request: Request,
    body: ConsultaRequest,
    tenant: TenantContext = Depends(get_tenant),
) -> EventSourceResponse:
    """Versión SSE de /consultar: emite progreso, la narración token por token y un evento final con
    el SQL y las filas. Mismas rejas que /consultar (ban → rate-limit → tamaño → anti-injection)."""
    ip = ip_cliente(request)

    if seguridad.esta_baneado(ip):
        raise HTTPException(
            status.HTTP_429_TOO_MANY_REQUESTS, "Demasiados intentos. Probá más tarde."
        )

    if seguridad.es_injection(body.message):
        seguridad.registrar_intento(ip)
        return EventSourceResponse(_stream_bloqueado())

    return EventSourceResponse(_stream_seguro(tenant, body.message))
