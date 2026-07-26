"""Política de fechas de los movimientos de cuenta corriente.

Vive acá y no en cada schema porque `ventas` y `compras` son ledgers espejo: la misma regla escrita
dos veces es la que después diverge. Un módulo, dos importadores.

**La ventana es política de la API, NO del dominio.** Los services aceptan cualquier fecha a
propósito: el importador de Paradox va a cargar años de historia por ahí, y no lo puede frenar una
regla pensada para atajar el dedo gordo de un operador. El límite se aplica solo donde entra input
hostil, que son los `*Crear`.
"""

from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

from app.core.config import get_settings

#: Cuánto se puede fechar para atrás desde la API. No es un número sagrado: es la distancia a la
#: que un error de tipeo (2025 en vez de 2026) deja de ser plausible y pasa a ser un desastre.
#: Correr el acumulado de un año entero en un ledger append-only solo se arregla con otro ajuste.
DIAS_RETROACTIVIDAD = 90


def hoy() -> date:
    """Qué día es hoy PARA EL NEGOCIO, no para el server.

    `date.today()` usa la zona del proceso, que en un contenedor es UTC. Este validador tiene que
    responder lo mismo que la base, que fecha con `current_date` en la zona de la sesión (ver el
    listener de `app/core/db.py`). Si los dos relojes se separan, el sistema termina guardando
    solo fechas que rechaza cuando se las mandan escritas — que es exactamente lo que pasaba entre
    las 21:00 y la medianoche argentina.
    """
    return datetime.now(ZoneInfo(get_settings().tz_negocio)).date()


def validar_fecha_movimiento(valor: date | None) -> date | None:
    """Valida la fecha de un movimiento cargado a mano. `None` = "hoy", y es válido.

    Pensada para un `field_validator` de Pydantic: levanta `ValueError`, que el schema traduce a un
    422 con el mensaje puesto.
    """
    if valor is None:
        return None

    limite = hoy()
    if valor > limite:
        raise ValueError("No se puede fechar un movimiento en el futuro.")

    if valor < limite - timedelta(days=DIAS_RETROACTIVIDAD):
        raise ValueError(
            f"No se puede fechar más de {DIAS_RETROACTIVIDAD} días para atrás. "
            "Si hay que corregir algo más viejo, cargá un ajuste con su motivo."
        )

    return valor
