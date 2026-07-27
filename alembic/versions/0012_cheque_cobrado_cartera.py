"""Agrega el concepto de egreso que le faltaba a la cartera de cheques

La 0011 congeló el vocabulario de conceptos, y al construir las transiciones de la cartera apareció
que le falta uno. No es un olvido de nomenclatura: es un hueco que hacía imposible escribir un
asiento correcto.

## El problema, en números

Un cheque de 15.000 entra por un recibo. `caja.asentar_documento` escribe:

    (forma='cheque', concepto='cobranza', ingreso=15000)   ->  saldo['cheque'] = 15000

Cuando ese cheque se cobra, entra plata al negocio por otra forma. Pero el cheque también tiene que
**salir de la cartera**, y ese egreso no tenía concepto legal:

    (forma='cheque', concepto='cheque_cobrado', egreso=15000)
        -> RECHAZADO por ck_caja_movimientos_concepto_coherente

porque `cheque_cobrado` está en el lado INGRESO del vocabulario. Sin la pata de egreso, la caja
quedaría diciendo `saldo['cheque']=15000` MÁS `saldo['efectivo']=15000`: 30.000 cuando en el
negocio hay 15.000. El doble, en silencio y en la tabla del dinero.

## La causa, que vale más que el arreglo

El vocabulario ata cada concepto a un signo, y eso es correcto para plata que entra o sale del
negocio. Pero **cobrar un cheque no es ninguna de las dos cosas: es una transferencia entre
formas** — el mismo hecho es egreso de una e ingreso de otra. Un vocabulario de un solo signo por
concepto no puede expresar eso con un solo valor; hacen falta los dos lados del par.

`cheque_cobrado_cartera` es la pata de egreso: el papel sale de la cartera. Su contrapartida es el
`cheque_cobrado` que ya existía: la plata entra por `efectivo` (cobro por ventanilla) o por
`transferencia` (el banco acreditó un cheque depositado).

Falta UN concepto y no varios porque las otras salidas de la cartera ya lo tenían: `rechazar` usa
`cheque_rechazado` y `entregar` usa `pago_proveedor`, los dos de egreso.

## Alcance

Solo AGREGA un valor permitido a dos CHECKs. Ninguna fila existente puede violar el constraint
nuevo, así que no hay backfill ni datos a migrar.

Revision ID: 0012
Revises: 0011
Create Date: 2026-07-27
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0012"
down_revision: str | None = "0011"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

#: Copia CONGELADA de `app.core.conceptos_caja`, como en la 0011: una migración no importa código
#: que cambia, o dejaría de reproducir el pasado. El candado que ata las dos copias es
#: `tests/test_caja_esquema.py::test_los_conceptos_de_python_y_el_check_de_la_base_coinciden`.
CONCEPTOS_INGRESO = (
    "cobranza",
    "cheque_cobrado",
    "anulacion_pago",
    "aporte",
    "otro_ingreso",
)

#: El vocabulario de egreso ANTERIOR a esta migración. Lo necesita el downgrade.
CONCEPTOS_EGRESO_0011 = (
    "pago_proveedor",
    "cheque_rechazado",
    "anulacion_cobranza",
    "gasto",
    "retiro",
    "otro_egreso",
)

CONCEPTOS_EGRESO = (
    *CONCEPTOS_EGRESO_0011,
    #: El cheque SALE de la cartera porque se cobró. Su contrapartida por la otra forma es el
    #: `cheque_cobrado` de arriba: juntos son un solo hecho con sus dos patas.
    "cheque_cobrado_cartera",
)

#: Los dos CHECKs que nombran conceptos. Postgres no sabe "agregar un valor a un IN": hay que
#: bajar el constraint y volver a crearlo con la lista completa.
_CHECK_CONCEPTO = "ck_caja_movimientos_concepto"
_CHECK_COHERENTE = "ck_caja_movimientos_concepto_coherente"


def _lista(valores: Sequence[str]) -> str:
    return ", ".join(f"'{v}'" for v in valores)


def _rehacer_checks(egresos: Sequence[str]) -> None:
    """Reescribe los dos CHECKs con el vocabulario de egreso que se le pase.

    Sirve para las dos direcciones: `upgrade` le pasa la lista con el concepto nuevo y `downgrade`
    la de la 0011. Tener una sola función evita que las dos copias se desincronicen, que es
    exactamente el tipo de error que este archivo existe para arreglar.
    """
    ingresos, egr = _lista(CONCEPTOS_INGRESO), _lista(egresos)

    op.drop_constraint(_CHECK_CONCEPTO, "caja_movimientos", type_="check")
    op.drop_constraint(_CHECK_COHERENTE, "caja_movimientos", type_="check")

    op.create_check_constraint(
        _CHECK_CONCEPTO, "caja_movimientos", f"concepto in ({ingresos}, {egr})"
    )
    # El invariante que hace que el vocabulario sirva de algo: un 'gasto' no puede ser un ingreso.
    op.create_check_constraint(
        _CHECK_COHERENTE,
        "caja_movimientos",
        f"(ingreso > 0 and concepto in ({ingresos})) or (egreso > 0 and concepto in ({egr}))",
    )


def upgrade() -> None:
    _rehacer_checks(CONCEPTOS_EGRESO)


def downgrade() -> None:
    """Restaura el vocabulario de la 0011.

    **Falla si ya hay filas con `cheque_cobrado_cartera`**, y está bien que falle: son cheques
    cobrados de verdad. Postgres valida el CHECK nuevo contra las filas existentes, así que el
    downgrade se planta con un error explícito en vez de borrar movimientos de dinero a espaldas
    de nadie. Si de verdad hay que bajar, primero se decide qué hacer con esos asientos.
    """
    _rehacer_checks(CONCEPTOS_EGRESO_0011)
