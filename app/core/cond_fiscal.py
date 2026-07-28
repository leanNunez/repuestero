"""Vocabulario de condiciones fiscales del cliente.

Vive en `core` por la misma razón que `core/formas_pago.py`: es una CONSTANTE DE VOCABULARIO, no
comportamiento.

Este campo no es una etiqueta descriptiva: **es el que decide qué comprobante se emite**. Un
responsable inscripto lleva factura A, un consumidor final B o C. Hasta ahora la columna era
`String(30)` libre y aceptaba cualquier cosa; el legacy cometió exactamente ese error con el CUIT
—texto libre, nunca validado— y la basura recién aparecía en la factura electrónica, cuando ya era
tarde. Se cierra ahora, antes de que exista AFIP, y no después.

`EXENTO` no está en uso hoy pero entra igual: Postgres no deja "ampliar" un CHECK, así que sumar un
valor más adelante cuesta una migración entera (drop + create con la lista completa).

Las migraciones NO importan esto: cada una congela su propia copia en el CHECK que crea (regla de
0008_compras.py). El candado que evita que las dos copias se separen es un test que inserta las
cuatro condiciones y verifica que la base las acepte.
"""

from typing import Literal

#: Las condiciones que la base acepta. Tiene que coincidir con el CHECK de la migración 0013.
CONDICIONES_FISCALES: frozenset[str] = frozenset(
    {"CONSUMIDOR_FINAL", "MONOTRIBUTO", "RESPONSABLE_INSCRIPTO", "EXENTO"}
)

#: El mismo catálogo como tipo, para que Pydantic rechace un valor inventado en el borde HTTP
#: (422 legible) antes de que llegue al service.
CondFiscalLiteral = Literal["CONSUMIDOR_FINAL", "MONOTRIBUTO", "RESPONSABLE_INSCRIPTO", "EXENTO"]

#: Con qué nace un cliente al que no le declaran condición. Es política de mostrador: el que compra
#: sin identificarse es consumidor final, que es además la opción más restrictiva (no da crédito
#: fiscal). Coincide con el `server_default` de la columna desde 0001.
COND_FISCAL_POR_DEFECTO = "CONSUMIDOR_FINAL"
