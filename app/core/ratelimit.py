"""Rate limiter compartido (slowapi). Se define acá para que router y main lo importen sin ciclo.

El estado vive en memoria → la app corre con 1 worker (o Redis en prod). Mismo criterio que el
baneo por strikes del asistente.
"""

from fastapi import Request
from slowapi import Limiter


def ip_cliente(request: Request) -> str:
    """La IP real del cliente, para banear y limitar.

    Vive acá y no en un router porque la política de en quién confiar para leer
    X-Forwarded-For tiene que ser UNA. Dos copias divergen, y la que quede floja es
    por donde un atacante rota IPs para saltarse el ban.

    En prod el contenedor no tiene IP pública propia: TODO lo que le llega pasa por el
    proxy de Render, así que la sola presencia de X-Forwarded-For ya implica que lo puso
    él. Por eso NO se filtra por peer TCP (esa condición nunca se cumple detrás de un
    proxy de red — solo detrás de uno en localhost, que no es el caso acá; con el filtro
    viejo esta rama era código muerto y todos los visitantes compartían un solo bucket).

    Se toma la entrada MÁS A LA DERECHA de la cadena, la que agrega el último proxy que
    tocó el request — no la izquierda, que la declara el cliente y es spoofeable
    (`X-Forwarded-For: 1.2.3.4` en el request original hace que el próximo proxy la
    agregue a la derecha de eso, nunca la reemplace).
    """
    fwd = request.headers.get("x-forwarded-for", "")
    if fwd:
        return fwd.split(",")[-1].strip()
    return request.client.host if request.client else "unknown"


# key_func=ip_cliente, NO slowapi.util.get_remote_address: esa función devuelve
# request.client.host a secas, sin mirar X-Forwarded-For — exactamente el peer del proxy
# de Render, el mismo bucket compartido que ip_cliente existe para evitar. Usarla acá dejaba
# el `20/minute` del asistente y el `6/minute` de la ingesta operando sobre un único bucket
# para todos los visitantes, aunque ip_cliente ya estuviera arreglado en el baneo por strikes.
limiter = Limiter(key_func=ip_cliente)
