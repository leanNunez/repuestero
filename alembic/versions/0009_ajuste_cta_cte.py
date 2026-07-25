"""Ajuste de cuenta corriente: motivo obligatorio y reversa única

El ledger es append-only desde la 0006 y el mensaje del trigger dice "corregí con un movimiento de
ajuste"... pero `tipo='ajuste'` nunca lo escribía nadie. Esta migración prepara el esquema para que
exista de verdad:

- `motivo`: por qué se ajustó. Nullable porque las filas históricas no tienen uno y no se puede
  backfillear una razón que nadie escribió; la obligatoriedad la impone un CHECK que solo aplica a
  `tipo='ajuste'`.
- Índice UNIQUE parcial sobre la reversa: hace IMPOSIBLE revertir dos veces el mismo movimiento.
  El service igual chequea antes para dar un error legible, pero un check-then-insert es carrera
  pura — dos clicks simultáneos duplicarían la corrección, y en un ledger que no se puede editar
  ese saldo queda mal para siempre. La base lo hace cumplir, no la buena voluntad del código
  (mismo criterio que el REVOKE + trigger de la 0006).

Los dos ledgers (cliente y proveedor) son espejos: todo va dos veces.

Revision ID: 0009
Revises: 0008
Create Date: 2026-07-25
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0009"
down_revision: str | None = "0008"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

#: Los dos libros mayores de cuenta corriente. Mismo esqueleto, mismas reglas.
LEDGERS = ("cta_cte_movimientos", "prov_cta_cte_movimientos")

#: `ref_tipo` que marca un movimiento como la reversa de otro. El `ref_id` apunta al original.
REF_REVERSA = "ajuste_de"


def upgrade() -> None:
    for tabla in LEDGERS:
        op.add_column(tabla, sa.Column("motivo", sa.String(200), nullable=True))

        # Un ajuste sin motivo escrito es una fila que en seis meses nadie puede explicar. No hace
        # falta backfill: todavía no existe ninguna fila con tipo='ajuste'.
        op.create_check_constraint(
            f"ck_{tabla}_ajuste_con_motivo",
            tabla,
            "tipo <> 'ajuste' or motivo is not null",
        )

        # Parcial: solo indexa las reversas, que son un puñado, y no las decenas de miles de
        # ventas y cobranzas. Le sirve de las dos cosas al service: la guarda de unicidad y el
        # lookup de "¿este movimiento ya fue revertido?" que necesita el extracto.
        op.execute(
            f"""
            create unique index uq_{tabla}_reversa
                on {tabla} (org_id, ref_id)
                where ref_tipo = '{REF_REVERSA}';
            """
        )


def downgrade() -> None:
    for tabla in LEDGERS:
        op.execute(f"drop index if exists uq_{tabla}_reversa;")
        op.drop_constraint(f"ck_{tabla}_ajuste_con_motivo", tabla, type_="check")
        op.drop_column(tabla, "motivo")
