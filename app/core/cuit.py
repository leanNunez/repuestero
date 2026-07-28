"""Validación de CUIT, compartida por todo el que dé de alta una persona o empresa.

Vivía en `clientes.service`. Se mudó acá cuando proveedores necesitó lo mismo: que
`proveedores` importara de `clientes` sería atarlos por un módulo que no tiene nada que ver con
ninguno de los dos. Es el mismo criterio con el que el `Numerador` salió de `ventas` hacia
`app/core/numeracion.py`.
"""

import re

_CUIT_RE = re.compile(r"^\d{2}-\d{8}-\d$")
_PESOS = (5, 4, 3, 2, 7, 6, 5, 4, 3, 2)


def cuit_valido(cuit: str) -> bool:
    """Valida formato y dígito verificador (módulo 11).

    El legacy guardaba el CUIT como texto libre y nunca lo validaba. Resultado: campos
    basura que después rompen la factura electrónica, cuando ya es tarde y el cliente
    está esperando en el mostrador. Se valida en la puerta de entrada, no en la salida.
    """
    if not _CUIT_RE.match(cuit):
        return False

    digitos = [int(d) for d in cuit.replace("-", "")]
    suma = sum(d * p for d, p in zip(digitos[:10], _PESOS, strict=True))
    resto = suma % 11
    verificador = 0 if resto == 0 else 11 - resto
    verificador = 9 if verificador == 10 else verificador

    return verificador == digitos[10]
