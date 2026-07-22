"""Orquestación del asistente: arma el ejecutor read-only del tenant y corre el grafo.

El servicio no sabe de LLMs ni de grafos por dentro: solo prepara el ejecutor de SQL (encerrado en
una sesión read-only con el tenant fijado) y delega en el grafo. La sesión read-only es efímera y
por-consulta: cada intento del grafo abre su propia transacción de solo lectura.
"""

import json
from collections.abc import Iterator
from uuid import UUID

from sqlalchemy import text
from sse_starlette.sse import ServerSentEvent

from app.asistente import grafo
from app.core.config import get_settings
from app.core.db import readonly_tenant_session
from app.core.rls import TenantContext


def _hacer_ejecutor(org_id: UUID, user_id: UUID):
    timeout = get_settings().asistente_timeout_ms

    def ejecutar(sql: str) -> list[dict]:
        # Sesión con rol app_readonly (no puede escribir) + tenant fijado por GUC (RLS lo encierra).
        with readonly_tenant_session(org_id, user_id, timeout_ms=timeout) as session:
            filas = session.execute(text(sql)).mappings().all()
            return [dict(fila) for fila in filas]

    return ejecutar


def consultar(tenant: TenantContext, mensaje: str) -> dict:
    return grafo.responder(mensaje, _hacer_ejecutor(tenant.org_id, tenant.user_id))


def _evento(event: str, **data) -> ServerSentEvent:
    # default=str: las filas pueden traer Decimal/UUID/date que json no serializa nativo.
    return ServerSentEvent(event=event, data=json.dumps(data, ensure_ascii=False, default=str))


def consultar_stream(tenant: TenantContext, mensaje: str) -> Iterator[ServerSentEvent]:
    """Versión streaming del asistente. Generador SYNC: Starlette lo corre en threadpool, así las
    llamadas bloqueantes a DB/LLM no bloquean el event loop.

    Emite: progreso(generando) → [progreso(redactando) → token×N → resultado] o error, y siempre fin.
    La fase de datos (generar+ejecutar, con reintentos y fallback a OpenAI) es atómica; recién con las
    filas en mano se streamea la narración token por token.
    """
    ejecutar = _hacer_ejecutor(tenant.org_id, tenant.user_id)

    yield _evento("progreso", fase="generando")
    datos = grafo.responder_datos(mensaje, ejecutar)

    if datos["filas"] is None:
        yield _evento(
            "error", mensaje="No pude armar una consulta válida para esa pregunta. ¿La reformulás?"
        )
        yield _evento("fin")
        return

    yield _evento("progreso", fase="redactando")
    for token in grafo.narrar_stream(mensaje, datos["filas"], datos["proveedor"], sql=datos["sql"]):
        yield _evento("token", texto=token)

    yield _evento("resultado", sql=datos["sql"], filas=datos["filas"])
    yield _evento("fin")
