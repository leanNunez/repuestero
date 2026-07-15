"""Rate limiter compartido (slowapi). Se define acá para que router y main lo importen sin ciclo.

El estado vive en memoria → la app corre con 1 worker (o Redis en prod). Mismo criterio que el
baneo por strikes del asistente.
"""

from slowapi import Limiter
from slowapi.util import get_remote_address

limiter = Limiter(key_func=get_remote_address)
