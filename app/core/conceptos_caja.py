"""Vocabulario de conceptos de caja: el "por qué" de cada movimiento de dinero.

Vive en `core` por la misma razón que `formas_pago.py`: es una CONSTANTE DE VOCABULARIO, no
comportamiento. La diferencia con aquel es que este catálogo tiene ESTRUCTURA — cada concepto
pertenece a un signo, y esa pertenencia es un invariante que la base hace cumplir.

Por qué no es una tabla `caja_conceptos` con su CRUD, como en el legacy (`IDConcepto`): un
catálogo editable por el usuario suena flexible hasta que alguien renombra "gasto" a "gastos
varios" y los reportes históricos dejan de agrupar. Estos siete son el vocabulario del dominio,
no preferencias. Si algún día hacen falta subcategorías del usuario, van en una columna aparte
sin tocar esto.

## Derivados vs manuales — el invariante central del módulo

Un movimiento de caja nace de una de dos formas, nunca de las dos:

- **DERIVADO**: lo emite un documento que ya existe (un recibo, una orden de pago, la
  transición de un cheque). El operador no lo carga: aparece solo, con `ref_tipo`/`ref_id`
  apuntando a su origen.
- **MANUAL**: no hay documento detrás (un flete, un retiro del dueño). Se carga a mano y
  `ref_tipo`/`ref_id` quedan en NULL.

**Si hay documento, caja NO se toca a mano.** Por eso `CONCEPTOS_DERIVADOS` existe: el endpoint
de carga manual los rechaza. Sin esa reja, un operador podría cargar "cobranza $5.000" a mano
además del recibo que ya la generó, y la caja diría el doble de lo que hay en el cajón — que es
exactamente el desastre que el legacy tenía y que este módulo existe para no repetir.

## Cuando un hecho tiene DOS patas

Un concepto lleva su signo pegado: `gasto` resta, `cobranza` suma, y el CHECK
`ck_caja_movimientos_concepto_coherente` lo hace cumplir. Eso alcanza para la plata que entra o
sale del negocio, que es la mayoría de los casos.

Pero **cobrar un cheque no entra ni sale: se mueve entre formas**. El papel deja la cartera y la
plata aparece en el cajón (o en el banco). Es UN hecho con DOS patas, y como cada concepto tiene
un solo signo, hacen falta dos valores:

- `cheque_cobrado_cartera` (egreso, forma `cheque`) — el papel sale de la cartera.
- `cheque_cobrado` (ingreso, forma `efectivo` o `transferencia`) — la plata entra.

Escribir solo la segunda pata fue el bug que motivó la migración 0012: la caja habría dicho que
tiene el cheque Y la plata, o sea el doble de lo que hay. Si algún día aparece otra transferencia
entre formas (un depósito de efectivo al banco, por ejemplo), sigue este mismo patrón de par.

Las salidas de cartera que NO son cobro ya tenían su concepto de egreso y no necesitaron uno
nuevo: `cheque_rechazado` cuando el banco lo devuelve, `pago_proveedor` cuando se endosa.

Las migraciones NO importan esto: cada una congela su propia copia en el CHECK que crea (misma
regla que `formas_pago`). El candado que evita que las copias se separen es un test que inserta
todos los conceptos y verifica que la base los acepte.
"""

from typing import Literal

#: Conceptos que SUMAN plata. Tiene que coincidir con el CHECK de la migración 0011.
CONCEPTOS_INGRESO: frozenset[str] = frozenset(
    {
        "cobranza",  # derivado: un recibo cobrado
        "cheque_cobrado",  # derivado: un cheque de la cartera que se hizo efectivo
        "anulacion_pago",  # derivado: anular una orden de pago devuelve la plata al cajón
        "aporte",  # manual: el dueño pone plata en la caja
        "otro_ingreso",  # manual: el cajón de sastre, a propósito último
    }
)

#: Conceptos que RESTAN plata.
CONCEPTOS_EGRESO: frozenset[str] = frozenset(
    {
        "pago_proveedor",  # derivado: una orden de pago emitida, o un cheque endosado
        "cheque_rechazado",  # derivado: un cheque que volvió, revierte su ingreso
        "cheque_cobrado_cartera",  # derivado: el cheque SALE de la cartera porque se cobró
        "anulacion_cobranza",  # derivado: anular un recibo saca lo que había entrado
        "gasto",  # manual: flete, librería, lo que sea que salga del cajón
        "retiro",  # manual: el dueño saca plata
        "otro_egreso",  # manual
    }
)

CONCEPTOS: frozenset[str] = CONCEPTOS_INGRESO | CONCEPTOS_EGRESO

#: Los que SOLO puede emitir el sistema, nunca el operador. Ver la explicación de arriba.
#: `cheque_cobrado` y `cheque_rechazado` están acá aunque su código llegue con la cartera: el
#: vocabulario se congela entero de una, porque agregarle un valor al CHECK después es otra
#: migración por algo que ya sabíamos hoy.
CONCEPTOS_DERIVADOS: frozenset[str] = frozenset(
    {
        "cobranza",
        "pago_proveedor",
        "cheque_cobrado",
        "cheque_cobrado_cartera",
        "cheque_rechazado",
        "anulacion_cobranza",
        "anulacion_pago",
    }
)

#: Lo que el endpoint de carga manual sí acepta.
CONCEPTOS_MANUALES: frozenset[str] = CONCEPTOS - CONCEPTOS_DERIVADOS

#: El mismo catálogo como tipo, para que Pydantic rechace un valor inventado en el borde HTTP
#: (422 legible) antes de que llegue al service.
ConceptoLiteral = Literal[
    "cobranza",
    "cheque_cobrado",
    "anulacion_pago",
    "aporte",
    "otro_ingreso",
    "pago_proveedor",
    "cheque_rechazado",
    "cheque_cobrado_cartera",
    "anulacion_cobranza",
    "gasto",
    "retiro",
    "otro_egreso",
]

#: Solo los manuales, como tipo. Es la reja del invariante en el borde HTTP: un payload con
#: `concepto: "cobranza"` muere en Pydantic con un 422, sin llegar al service.
ConceptoManualLiteral = Literal["aporte", "otro_ingreso", "gasto", "retiro", "otro_egreso"]


def es_ingreso(concepto: str) -> bool:
    """De qué lado del libro cae un concepto. La base impone lo mismo con un CHECK; esto es para
    que el service no tenga que repetir el `in` en cada llamada."""
    return concepto in CONCEPTOS_INGRESO
