"""Cierra el vocabulario de `clientes.cond_fiscal` con un CHECK

Desde la 0001 la columna es `String(30)` libre con `server_default='CONSUMIDOR_FINAL'`. Acepta
cualquier texto. Los tres valores que se usan hoy están ahí por convención, no porque algo los
obligue.

## Por qué ahora

`cond_fiscal` **decide qué comprobante se emite**: responsable inscripto → factura A, consumidor
final → B o C. Con el alta por API, el valor deja de venir de un seed escrito por nosotros y pasa a
venir de una persona en el mostrador. El legacy ya cometió este error con el CUIT —texto libre,
nunca validado— y la basura recién se descubría al emitir la factura. El momento de cerrarlo es
antes de que exista AFIP, no después: con facturas ya emitidas, un dato mal cargado no se corrige,
se rectifica.

## Alcance

Solo agrega un CHECK. Verificado contra la base local antes de escribir esta migración:

    RESPONSABLE_INSCRIPTO -> 660
    MONOTRIBUTO           -> 648
    CONSUMIDOR_FINAL      -> 504

Los tres están en el vocabulario, así que ninguna fila existente viola el constraint y no hay
backfill. `EXENTO` entra sin uso actual porque Postgres no permite ampliar un CHECK: sumarlo después
costaría drop + create con la lista entera.

Si en otra base apareciera un valor fuera de la lista, `create_check_constraint` **falla acá** — y
eso es lo correcto: es un dato que hay que mirar, no normalizar en silencio.

Revision ID: 0013
Revises: 0012
Create Date: 2026-07-27
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0013"
down_revision: str | None = "0012"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

#: Copia CONGELADA de `app.core.cond_fiscal`, como en la 0011 y la 0012: una migración no importa
#: código que cambia, o dejaría de reproducir el pasado. El candado que ata las dos copias es
#: `tests/test_clientes.py::test_las_condiciones_de_python_y_el_check_de_la_base_coinciden`.
CONDICIONES_FISCALES = (
    "CONSUMIDOR_FINAL",
    "MONOTRIBUTO",
    "RESPONSABLE_INSCRIPTO",
    "EXENTO",
)

_CHECK = "ck_clientes_cond_fiscal"


def _lista_sql(valores: tuple[str, ...]) -> str:
    return ", ".join(f"'{v}'" for v in valores)


def upgrade() -> None:
    op.create_check_constraint(
        _CHECK,
        "clientes",
        f"cond_fiscal in ({_lista_sql(CONDICIONES_FISCALES)})",
    )


def downgrade() -> None:
    op.drop_constraint(_CHECK, "clientes", type_="check")
