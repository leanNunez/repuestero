"""Identidad fiscal: condición del emisor y documento del receptor

Para armar un comprobante electrónico hacen falta dos datos que hoy no existen en ninguna tabla:
**qué es fiscalmente la organización que emite** y **con qué documento se identifica el cliente
que recibe**.

## Por qué ahora

La condición del emisor decide la LETRA: un responsable inscripto emite A o B, un monotributista
siempre C. Hoy `organizaciones` solo tiene `nombre`, `cuit` y `activa` — no hay forma de saber qué
letra corresponde. Y del lado del receptor, ARCA pide `DocTipo` + `DocNro`, no un CUIT suelto: un
consumidor final que se identifica con DNI no tiene hoy dónde guardarlo, así que viajaría como
anónimo aunque haya dado su documento.

Es el mismo criterio de la 0013: cerrar el dato antes de que exista AFIP. Con comprobantes ya
emitidos, un dato fiscal mal cargado no se corrige, se rectifica.

## Alcance

Solo agrega columnas nullable y sus CHECK. **No hay backfill y es deliberado.**

Verificado contra la base local antes de escribir esta migración:

    organizaciones            -> 6 filas, 0 con CUIT
    clientes RESPONSABLE_INSCRIPTO -> 664 (664 con CUIT)
    clientes MONOTRIBUTO           -> 648 (648 con CUIT)
    clientes CONSUMIDOR_FINAL      -> 510 (  1 con CUIT)

**`organizaciones.cond_fiscal` queda NULL en las seis.** Inventarle una condición fiscal a una
organización es inventar un hecho fiscal, y ninguna podría facturar igual: no tienen CUIT. Una org
sin `cond_fiscal` simplemente no emite comprobantes electrónicos; el error se levanta al facturar,
con un mensaje que dice qué falta configurar.

**`clientes.doc_tipo`/`doc_nro` quedan NULL en las 1822.** No se derivan del CUIT en un UPDATE
masivo porque no hace falta: `app/core/documentos.py::documento_de` ya cae al CUIT cuando no hay
documento explícito, y los 1312 clientes con CUIT viajan correctos como `DocTipo=80` sin tocar una
sola fila. Los 509 consumidores finales sin CUIT viajan como `(99, 0)`, que es la verdad.

`CONSUMIDOR_FINAL` NO está entre las condiciones del emisor, y no es un olvido: un consumidor final
no emite comprobantes, los recibe. La reja va en la base y no solo en Python porque una
organización mal configurada no se descubre al guardarla sino al facturar.

Revision ID: 0014
Revises: 0013
Create Date: 2026-08-07
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0014"
down_revision: str | None = "0013"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

#: Copia CONGELADA de `app.core.cond_fiscal.CONDICIONES_FISCALES_EMISOR`, como en la 0013: una
#: migración no importa código que cambia, o dejaría de reproducir el pasado. El candado que ata
#: las dos copias es
#: `tests/test_identidad_fiscal.py::test_las_condiciones_del_emisor_de_python_y_de_la_base_coinciden`.
CONDICIONES_FISCALES_EMISOR = (
    "RESPONSABLE_INSCRIPTO",
    "MONOTRIBUTO",
    "EXENTO",
)

#: Copia CONGELADA de `app.core.arca.DOC_TIPOS`. Entran los doce que ARCA acepta y no solo los tres
#: que el mostrador usa (CUIT, DNI, sin identificar): Postgres no deja ampliar un CHECK, así que
#: sumar el pasaporte más adelante costaría drop + create con la lista entera.
DOC_TIPOS = (80, 86, 87, 89, 90, 91, 92, 93, 94, 95, 96, 99)

_CHECK_EMISOR = "ck_organizaciones_cond_fiscal"
_CHECK_DOC_TIPO = "ck_clientes_doc_tipo"
_CHECK_DOC_PAR = "ck_clientes_doc_par"


def _lista_sql(valores: tuple[str, ...]) -> str:
    return ", ".join(f"'{v}'" for v in valores)


def upgrade() -> None:
    op.add_column("organizaciones", sa.Column("cond_fiscal", sa.String(30), nullable=True))
    op.create_check_constraint(
        _CHECK_EMISOR,
        "organizaciones",
        f"cond_fiscal is null or cond_fiscal in ({_lista_sql(CONDICIONES_FISCALES_EMISOR)})",
    )

    op.add_column("clientes", sa.Column("doc_tipo", sa.Integer(), nullable=True))
    op.add_column("clientes", sa.Column("doc_nro", sa.String(11), nullable=True))
    op.create_check_constraint(
        _CHECK_DOC_TIPO,
        "clientes",
        f"doc_tipo is null or doc_tipo in ({', '.join(str(d) for d in DOC_TIPOS)})",
    )
    # Un documento a medias no se puede declarar: ocho dígitos sin tipo no dicen si son un DNI o un
    # pasaporte, y un tipo sin número no identifica a nadie. O están los dos o no está ninguno.
    op.create_check_constraint(
        _CHECK_DOC_PAR,
        "clientes",
        "(doc_tipo is null) = (doc_nro is null)",
    )


def downgrade() -> None:
    op.drop_constraint(_CHECK_DOC_PAR, "clientes", type_="check")
    op.drop_constraint(_CHECK_DOC_TIPO, "clientes", type_="check")
    op.drop_column("clientes", "doc_nro")
    op.drop_column("clientes", "doc_tipo")

    op.drop_constraint(_CHECK_EMISOR, "organizaciones", type_="check")
    op.drop_column("organizaciones", "cond_fiscal")
