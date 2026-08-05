"""Formato de importes para los textos que LEE una persona.

Solo para mensajes (advertencias, avisos). Los importes de las respuestas viajan como `Decimal`
y los formatea el front — acá no se toca eso.

Existe porque `f"{monto:,.2f}"` produce el formato de EE.UU. (`9,506.97`), y este es un sistema
argentino: la misma pantalla que muestra `$ 9.506,97` no puede decir `9,506.97` dos líneas más
abajo. Se ve como dos números distintos.
"""

from decimal import Decimal


def pesos(monto: Decimal) -> str:
    """`9506.97` → `"9.506,97"`. Punto de miles y coma decimal, como en `docs/art-direction.md`.

    El paso por `_` es para no pisar lo ya reemplazado: sin él, la coma que acaba de entrar como
    separador decimal se volvería a convertir en punto.
    """
    return f"{monto:,.2f}".replace(",", "_").replace(".", ",").replace("_", ".")
