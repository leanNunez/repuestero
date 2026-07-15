"""Orquestación del asistente: arma el ejecutor read-only del tenant y corre el grafo.

El servicio no sabe de LLMs ni de grafos por dentro: solo prepara el ejecutor de SQL (encerrado en
una sesión read-only con el tenant fijado) y delega en el grafo. La sesión read-only es efímera y
por-consulta: cada intento del grafo abre su propia transacción de solo lectura.
"""

from uuid import UUID

from sqlalchemy import text

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
