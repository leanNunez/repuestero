"""Rate limiter compartido (slowapi). Se define acá para que router y main lo importen sin ciclo.

El estado vive en memoria → la app corre con 1 worker (o Redis en prod). Mismo criterio que el
baneo por strikes del asistente.
"""

from fastapi import Request
from slowapi import Limiter
from slowapi.util import get_remote_address

limiter = Limiter(key_func=get_remote_address)

# Solo se confía en X-Forwarded-For si viene de un proxy conocido (spoofeable si no).
_PROXIES_CONFIABLES = {"127.0.0.1", "::1"}


def ip_cliente(request: Request) -> str:
    """La IP real del cliente, para banear y limitar.

    Vive acá y no en un router porque la política de en quién confiar para leer
    X-Forwarded-For tiene que ser UNA. Dos copias divergen, y la que quede floja es
    por donde un atacante rota IPs para saltarse el ban.
    """
    ip = request.client.host if request.client else "unknown"
    if ip in _PROXIES_CONFIABLES:
        fwd = request.headers.get("x-forwarded-for", "")
        if fwd:
            return fwd.split(",")[0].strip()
    return ip
