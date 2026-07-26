"""Recibo de cobranza y orden de pago, con su detalle de formas de pago

Cierra el agujero de la cuenta corriente: hasta acá una cobranza escribía un Haber SUELTO, con
`ref_tipo`/`ref_id` en NULL, porque no existía el documento al que apuntar. Todos los demás
movimientos del ledger sí referencian el suyo (venta -> 'comprobante', NC -> 'nota_credito').

- `recibos` + `recibo_formas_pago`: el comprobante del cobro a un cliente y con qué se cobró.
- `ordenes_pago` + `orden_pago_formas_pago`: el espejo del lado proveedor.

Las CUATRO tablas se crean acá aunque el código de compras llegue en un PR posterior: el DDL de
las dos familias es idéntico y separarlo en dos migraciones duplicaría dos funciones de trigger,
dos blindajes append-only, dos policies de RLS y dos triggers de suma para no dejar una tabla
vacía durante un PR. Es lo mismo que hizo la 0009 con los dos ledgers.

NO se hace backfill de las cobranzas existentes. Un recibo retroactivo sería un documento
falsificado: le asignaría números correlativos que nunca se imprimieron ni se entregaron, y a
partir de ahí la numeración los reclamaría como emitidos. Las cobranzas anteriores a esta
migración se quedan con la referencia en NULL, que es la verdad.

Revision ID: 0010
Revises: 0009
Create Date: 2026-07-25
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0010"
down_revision: str | None = "0009"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

#: El rol DML de la app. Hardcodeado a propósito: cada migración es un snapshot y solo conoce
#: lo que ella misma crea (ver la nota en 0001_esquema_nucleo.py).
APP_ROLE = "app_user"

#: Copia CONGELADA de `app.core.formas_pago.FORMAS_PAGO`. No se importa: una migración no puede
#: depender de código que cambia, o dejaría de reproducir el pasado. Un test verifica que las dos
#: copias sigan coincidiendo.
FORMAS_PAGO = ("efectivo", "cheque", "transferencia", "tarjeta")

#: Las dos familias documento/detalle. Mismo DDL, distinta cuenta y distinto numerador.
FAMILIAS = (
    {
        "padre": "recibos",
        "hijo": "recibo_formas_pago",
        "fk_hijo": "recibo_id",
        "cuenta_col": "cliente_id",
        "cuenta_tabla": "clientes",
        "funcion_append": "recibo_append_only",
        "funcion_suma": "recibo_formas_cierran",
        "leyenda": "un recibo no se edita: revertí el movimiento de cuenta corriente con un ajuste",
    },
    {
        "padre": "ordenes_pago",
        "hijo": "orden_pago_formas_pago",
        "fk_hijo": "orden_pago_id",
        "cuenta_col": "proveedor_id",
        "cuenta_tabla": "proveedores",
        "funcion_append": "orden_pago_append_only",
        "funcion_suma": "orden_pago_formas_cierran",
        "leyenda": (
            "una orden de pago no se edita: revertí el movimiento de cuenta corriente con un ajuste"
        ),
    },
)


def _org_fk(nullable: bool = False):
    return sa.Column(
        "org_id",
        sa.Uuid(),
        sa.ForeignKey("organizaciones.id", ondelete="CASCADE"),
        nullable=nullable,
        index=True,
    )


def _aplicar_rls(tabla: str) -> None:
    """RLS estándar por tenant. `force` porque el owner está exento por defecto; `with check`
    además de `using` para que un tenant no pueda ESCRIBIR filas dentro de otro."""
    op.execute(f"alter table {tabla} enable row level security;")
    op.execute(f"alter table {tabla} force row level security;")
    op.execute(
        f"""
        create policy tenant_isolation on {tabla}
            using      (org_id = current_setting('app.current_org_id', true)::uuid)
            with check (org_id = current_setting('app.current_org_id', true)::uuid);
        """
    )


def _blindar_append_only(tabla: str, funcion: str) -> None:
    """Append-only de verdad: la base lo hace cumplir, no la buena voluntad del código."""
    op.execute(f"revoke update, delete on {tabla} from {APP_ROLE};")
    op.execute(
        f"""
        create trigger trg_{tabla}_append_only
        before update or delete on {tabla}
        for each row execute function {funcion}();
        """
    )


def _crear_familia(f: dict[str, str]) -> None:
    padre, hijo = f["padre"], f["hijo"]

    op.create_table(
        padre,
        sa.Column("id", sa.BigInteger(), sa.Identity(always=True), primary_key=True),
        _org_fk(),
        sa.Column(
            f["cuenta_col"],
            sa.BigInteger(),
            sa.ForeignKey(f"{f['cuenta_tabla']}.id", ondelete="RESTRICT"),
            nullable=False,
            index=True,
        ),
        # 'REC' / 'OP'. Existe aunque hoy cada tabla tenga un solo valor: el unique de abajo
        # espeja el de `comprobantes`, y deja escrito en la fila QUÉ numerador la produjo.
        sa.Column("tipo", sa.String(10), nullable=False),
        sa.Column("pto_venta", sa.Integer(), nullable=False),
        sa.Column("numero", sa.BigInteger(), nullable=False),
        sa.Column("fecha", sa.Date(), nullable=False, server_default=sa.func.current_date()),
        sa.Column("total", sa.Numeric(14, 2), nullable=False),
        sa.Column("creado_en", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("creado_por", sa.Uuid(), nullable=True),
        sa.UniqueConstraint(
            "org_id", "tipo", "pto_venta", "numero", name=f"uq_{padre}_org_tipo_pv_num"
        ),
        # Destino de la FK compuesta del hijo. Redundante como unicidad (`id` ya es PK), pero
        # Postgres exige un unique sobre las columnas exactas que referencia una FK.
        sa.UniqueConstraint("org_id", "id", name=f"uq_{padre}_org_id"),
        sa.CheckConstraint("total > 0", name=f"ck_{padre}_total_positivo"),
    )

    formas = ", ".join(f"'{x}'" for x in FORMAS_PAGO)
    op.create_table(
        hijo,
        sa.Column("id", sa.BigInteger(), sa.Identity(always=True), primary_key=True),
        _org_fk(),
        sa.Column(f["fk_hijo"], sa.BigInteger(), nullable=False, index=True),
        sa.Column("forma", sa.String(20), nullable=False),
        sa.Column("monto", sa.Numeric(14, 2), nullable=False),
        sa.Column("creado_en", sa.DateTime(timezone=True), server_default=sa.func.now()),
        # FK COMPUESTA, a diferencia de `comprobante_items`, que usa una simple. Con una FK simple
        # un renglón podría apuntar al documento de OTRA organización: el trigger de suma corre
        # bajo RLS, no vería ese documento, y dejaría pasar el renglón EN SILENCIO. Acá es gratis
        # cerrarlo porque la tabla se está creando.
        sa.ForeignKeyConstraint(
            ["org_id", f["fk_hijo"]],
            [f"{padre}.org_id", f"{padre}.id"],
            name=f"fk_{hijo}_{padre}",
            ondelete="CASCADE",
        ),
        # Sin unique (documento, forma): dos cheques distintos en el mismo recibo son dos
        # renglones legítimos. Es la razón estructural de que el detalle sea 1:N.
        sa.CheckConstraint(f"forma in ({formas})", name=f"ck_{hijo}_forma"),
        sa.CheckConstraint("monto > 0", name=f"ck_{hijo}_monto_positivo"),
    )

    for tabla in (padre, hijo):
        _aplicar_rls(tabla)

    op.execute(
        f"""
        create or replace function {f["funcion_append"]}() returns trigger as $$
        begin
            raise exception '{f["leyenda"]}';
        end;
        $$ language plpgsql;
        """
    )
    _blindar_append_only(padre, f["funcion_append"])
    _blindar_append_only(hijo, f["funcion_append"])

    # El invariante que un CHECK no puede expresar: las formas de pago tienen que sumar EXACTO el
    # total del documento. `_blindar_append_only` revoca UPDATE y DELETE pero NO INSERT, así que
    # sin esto cualquiera (el importador, una sesión de psql, el futuro app/caja/) puede meter un
    # renglón de más en un documento ya cerrado — en una tabla append-only, o sea sin arreglo.
    #
    # DIFERIDO es obligatorio: los hijos entran DESPUÉS del padre por la FK, y un trigger
    # inmediato vería suma 0 y rechazaría todo. Se evalúa recién en el COMMIT.
    #
    # También va sobre el PADRE: sin eso, un documento con CERO renglones no dispara nada (el
    # trigger del hijo no corre si no hay hijos), que es justo el caso que más importa.
    op.execute(
        f"""
        create or replace function {f["funcion_suma"]}() returns trigger as $$
        declare
            _id    bigint;
            _total numeric(14,2);
            _suma  numeric(14,2);
        begin
            -- Dos ramas y no un `case` de una línea: plpgsql prepara la expresión ENTERA, así que
            -- un `case` que nombre `new.{f["fk_hijo"]}` explota al correr sobre `{padre}`, donde ese
            -- campo no existe. Cada asignación suelta se prepara solo si se ejecuta.
            if tg_table_name = '{padre}' then
                _id := new.id;
            else
                _id := new.{f["fk_hijo"]};
            end if;

            -- Corre como SECURITY INVOKER: si el documento es de otra organización, el RLS lo
            -- esconde y no hay nada que validar. La FK compuesta es la que impide llegar acá.
            select total into _total from {padre} where id = _id;
            if not found then
                return null;
            end if;

            select coalesce(sum(monto), 0) into _suma
              from {hijo} where {f["fk_hijo"]} = _id;

            if _suma <> _total then
                raise exception
                    'las formas de pago del documento % suman % y el documento dice %',
                    _id, _suma, _total
                    using errcode = 'check_violation';
            end if;
            return null;
        end;
        $$ language plpgsql;
        """
    )
    # `errcode = 'check_violation'` para que psycopg levante IntegrityError y no un DatabaseError
    # genérico: así el router lo distingue y los tests lo pueden afirmar.
    for tabla in (padre, hijo):
        op.execute(
            f"""
            create constraint trigger trg_{tabla}_formas_cierran
            after insert on {tabla}
            deferrable initially deferred
            for each row execute function {f["funcion_suma"]}();
            """
        )


def upgrade() -> None:
    for familia in FAMILIAS:
        _crear_familia(familia)

    # Sin GRANT explícito sobre las tablas: los `alter default privileges` de la 0003 ya cubren
    # a app_user (DML) y app_readonly (SELECT).


def downgrade() -> None:
    for familia in FAMILIAS:
        op.execute(f"drop table if exists {familia['hijo']} cascade;")
        op.execute(f"drop table if exists {familia['padre']} cascade;")
        op.execute(f"drop function if exists {familia['funcion_append']}();")
        op.execute(f"drop function if exists {familia['funcion_suma']}();")
