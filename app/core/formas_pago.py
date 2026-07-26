"""Vocabulario de formas de pago, compartido por el recibo (ventas) y la orden de pago (compras).

Vive en `core` por la misma razón que `core/fechas.py`: es una CONSTANTE DE VOCABULARIO, no
comportamiento. Ventas y compras duplican su lógica a propósito (ver `registrar_ajuste`, escrito
dos veces), pero el catálogo de formas tiene que ser idéntico en las dos familias para que el
futuro `app/caja/` pueda leerlas uniformemente sin preguntar de qué lado vino el movimiento.

Las migraciones NO importan esto: cada una congela su propia copia en el CHECK que crea (regla de
0008_compras.py). El candado que evita que las dos copias se separen es un test que inserta las
cuatro formas de `FORMAS_PAGO` y verifica que la base las acepte.

En esta etapa `cheque` es solo una etiqueta con su monto. Los datos del cheque —banco, número,
fecha de cobro, conciliación— llegan con el módulo de caja, y ahí cada renglón de forma de pago
se convierte en un cheque de la cartera. Esa es la razón de que el detalle sea 1:N y no una
columna: un recibo puede cancelarse con dos cheques distintos.
"""

from typing import Literal

#: Las formas que la base acepta. Tiene que coincidir con el CHECK de la migración 0010.
FORMAS_PAGO: frozenset[str] = frozenset({"efectivo", "cheque", "transferencia", "tarjeta"})

#: El mismo catálogo como tipo, para que Pydantic rechace un valor inventado en el borde HTTP
#: (422 legible) antes de que llegue al service.
FormaPagoLiteral = Literal["efectivo", "cheque", "transferencia", "tarjeta"]

#: Con qué se asume que pagaron cuando el cliente HTTP no manda el detalle. Es política de
#: mostrador, no del dominio: el service siempre exige el dato (ver `registrar_cobranza`).
FORMA_POR_DEFECTO = "efectivo"
