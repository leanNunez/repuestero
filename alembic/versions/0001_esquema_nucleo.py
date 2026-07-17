"""Esquema núcleo + vista stock + RLS multi-tenant

Revision ID: 0001
Revises:
Create Date: 2026-07-14
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

APP_ROLE = "app_user"

#: Las tablas con org_id que existían al momento de esta migración. Es una copia
#: congelada de `core.registry.TABLAS_TENANT`, NO un import: una migración es un
#: snapshot inmutable del esquema en un punto del tiempo. Si importara la tupla viva,
#: agregar un feature nuevo al registry haría que esta migración intente aplicar RLS
#: sobre una tabla que todavía no existe. Cada migración posterior aplica RLS a las
#: tablas que ella misma crea.
TABLAS_TENANT_0001: tuple[str, ...] = (
    "articulos",
    "listas_precio",
    "articulo_precios",
    "depositos",
    "stock_movimientos",
    "clientes",
    "proveedores",
    "articulo_proveedores",
    "vehiculos",
    "articulo_aplicaciones",
)


def _org_fk() -> sa.Column:
    return sa.Column(
        "org_id",
        sa.Uuid(),
        sa.ForeignKey("organizaciones.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )


def _creado_en() -> sa.Column:
    return sa.Column("creado_en", sa.DateTime(timezone=True), server_default=sa.func.now())


def upgrade() -> None:
    # ---------------------------------------------------------------- tenant raíz
    op.create_table(
        "organizaciones",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("nombre", sa.String(120), nullable=False),
        sa.Column("cuit", sa.String(13)),
        sa.Column("activa", sa.Boolean(), nullable=False, server_default=sa.true()),
        _creado_en(),
    )

    op.create_table(
        "miembros",
        sa.Column("id", sa.BigInteger(), sa.Identity(always=True), primary_key=True),
        _org_fk(),
        sa.Column("user_id", sa.Uuid(), nullable=False, index=True),
        sa.Column("rol", sa.String(30), nullable=False, server_default="operador"),
        _creado_en(),
        sa.UniqueConstraint("org_id", "user_id", name="uq_miembros_org_user"),
    )

    # ---------------------------------------------------------------- catálogo
    op.create_table(
        "listas_precio",
        sa.Column("id", sa.BigInteger(), sa.Identity(always=True), primary_key=True),
        _org_fk(),
        sa.Column("codigo", sa.String(30), nullable=False),
        sa.Column("nombre", sa.String(80), nullable=False),
        _creado_en(),
        sa.UniqueConstraint("org_id", "codigo", name="uq_listas_org_codigo"),
    )

    op.create_table(
        "articulos",
        sa.Column("id", sa.BigInteger(), sa.Identity(always=True), primary_key=True),
        _org_fk(),
        sa.Column("codigo", sa.String(40), nullable=False),
        sa.Column("detalle", sa.String(200), nullable=False),
        sa.Column("costo", sa.Numeric(14, 4), nullable=False, server_default="0"),
        sa.Column("costo_dolar", sa.Numeric(14, 4)),
        sa.Column("alicuota_iva", sa.Numeric(5, 2), nullable=False, server_default="21.00"),
        sa.Column("punto_pedido", sa.Numeric(14, 2), nullable=False, server_default="0"),
        sa.Column("codigo_barra", sa.String(60)),
        sa.Column("marca", sa.String(60)),
        sa.Column("rubro", sa.String(60)),
        sa.Column("activo", sa.Boolean(), nullable=False, server_default=sa.true()),
        _creado_en(),
        sa.UniqueConstraint("org_id", "codigo", name="uq_articulos_org_codigo"),
    )

    op.create_table(
        "articulo_precios",
        sa.Column("id", sa.BigInteger(), sa.Identity(always=True), primary_key=True),
        _org_fk(),
        sa.Column(
            "articulo_id",
            sa.BigInteger(),
            sa.ForeignKey("articulos.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column(
            "lista_id",
            sa.BigInteger(),
            sa.ForeignKey("listas_precio.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column("precio", sa.Numeric(14, 2), nullable=False),
        sa.Column("margen", sa.Numeric(6, 2)),
        _creado_en(),
        sa.UniqueConstraint("articulo_id", "lista_id", name="uq_precio_articulo_lista"),
    )

    # ---------------------------------------------------------------- proveedores
    op.create_table(
        "proveedores",
        sa.Column("id", sa.BigInteger(), sa.Identity(always=True), primary_key=True),
        _org_fk(),
        sa.Column("codigo", sa.String(20), nullable=False),
        sa.Column("razon_social", sa.String(120), nullable=False),
        sa.Column("cuit", sa.String(13)),
        sa.Column("telefono", sa.String(40)),
        sa.Column("email", sa.String(120)),
        sa.Column("activo", sa.Boolean(), nullable=False, server_default=sa.true()),
        _creado_en(),
        sa.UniqueConstraint("org_id", "codigo", name="uq_proveedores_org_codigo"),
    )

    op.create_table(
        "articulo_proveedores",
        sa.Column("id", sa.BigInteger(), sa.Identity(always=True), primary_key=True),
        _org_fk(),
        sa.Column(
            "articulo_id",
            sa.BigInteger(),
            sa.ForeignKey("articulos.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column(
            "proveedor_id",
            sa.BigInteger(),
            sa.ForeignKey("proveedores.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column("codigo_proveedor", sa.String(40)),
        sa.Column("costo", sa.Numeric(14, 4), nullable=False, server_default="0"),
        sa.Column("es_preferido", sa.Boolean(), nullable=False, server_default=sa.false()),
        _creado_en(),
        sa.UniqueConstraint(
            "articulo_id", "proveedor_id", name="uq_artprov_articulo_proveedor"
        ),
    )

    # ---------------------------------------------------------------- clientes
    op.create_table(
        "clientes",
        sa.Column("id", sa.BigInteger(), sa.Identity(always=True), primary_key=True),
        _org_fk(),
        sa.Column("codigo", sa.String(20), nullable=False),
        sa.Column("denominacion", sa.String(140), nullable=False),
        sa.Column("cuit", sa.String(13)),
        sa.Column(
            "cond_fiscal", sa.String(30), nullable=False, server_default="CONSUMIDOR_FINAL"
        ),
        sa.Column("limite_cta_cte", sa.Numeric(14, 2), nullable=False, server_default="0"),
        sa.Column(
            "lista_precio_id",
            sa.BigInteger(),
            sa.ForeignKey("listas_precio.id", ondelete="SET NULL"),
        ),
        sa.Column("telefono", sa.String(40)),
        sa.Column("email", sa.String(120)),
        sa.Column("direccion", sa.String(160)),
        sa.Column("activo", sa.Boolean(), nullable=False, server_default=sa.true()),
        _creado_en(),
        sa.UniqueConstraint("org_id", "codigo", name="uq_clientes_org_codigo"),
    )

    # ---------------------------------------------------------------- compatibilidad
    op.create_table(
        "vehiculos",
        sa.Column("id", sa.BigInteger(), sa.Identity(always=True), primary_key=True),
        _org_fk(),
        sa.Column("marca", sa.String(40), nullable=False),
        sa.Column("modelo", sa.String(60), nullable=False),
        sa.Column("anio_desde", sa.Integer()),
        sa.Column("anio_hasta", sa.Integer()),
        sa.Column("motor", sa.String(40)),
        sa.Column("version", sa.String(60)),
        _creado_en(),
        sa.UniqueConstraint(
            "org_id",
            "marca",
            "modelo",
            "anio_desde",
            "anio_hasta",
            "motor",
            "version",
            name="uq_vehiculos_identidad",
        ),
    )

    op.create_table(
        "articulo_aplicaciones",
        sa.Column("id", sa.BigInteger(), sa.Identity(always=True), primary_key=True),
        _org_fk(),
        sa.Column(
            "articulo_id",
            sa.BigInteger(),
            sa.ForeignKey("articulos.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column(
            "vehiculo_id",
            sa.BigInteger(),
            sa.ForeignKey("vehiculos.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column("nota", sa.String(200)),
        sa.Column("origen", sa.String(30), nullable=False, server_default="manual"),
        sa.Column("confirmado", sa.Boolean(), nullable=False, server_default=sa.false()),
        _creado_en(),
        sa.UniqueConstraint(
            "articulo_id", "vehiculo_id", name="uq_aplicacion_articulo_vehiculo"
        ),
    )

    # ---------------------------------------------------------------- inventario
    op.create_table(
        "depositos",
        sa.Column("id", sa.BigInteger(), sa.Identity(always=True), primary_key=True),
        _org_fk(),
        sa.Column("codigo", sa.String(20), nullable=False),
        sa.Column("nombre", sa.String(80), nullable=False),
        _creado_en(),
        sa.UniqueConstraint("org_id", "codigo", name="uq_depositos_org_codigo"),
    )

    op.create_table(
        "stock_movimientos",
        sa.Column("id", sa.BigInteger(), sa.Identity(always=True), primary_key=True),
        _org_fk(),
        sa.Column(
            "articulo_id",
            sa.BigInteger(),
            sa.ForeignKey("articulos.id", ondelete="RESTRICT"),
            nullable=False,
            index=True,
        ),
        sa.Column(
            "deposito_id",
            sa.BigInteger(),
            sa.ForeignKey("depositos.id", ondelete="RESTRICT"),
            nullable=False,
            index=True,
        ),
        sa.Column("cantidad", sa.Numeric(14, 2), nullable=False),
        sa.Column("motivo", sa.String(30), nullable=False),
        sa.Column("ref_tipo", sa.String(30)),
        sa.Column("ref_id", sa.BigInteger()),
        _creado_en(),
        sa.Column("creado_por", sa.Uuid()),
    )
    op.create_index(
        "ix_stock_mov_lookup",
        "stock_movimientos",
        ["org_id", "articulo_id", "deposito_id"],
    )

    _crear_vista_stock()
    _blindar_kardex()
    _aplicar_rls()


def _crear_vista_stock() -> None:
    """El stock es la SUMA del kardex. No una columna mutable que se pueda desincronizar.

    `security_invoker = true` es OBLIGATORIO (Postgres 15+): sin eso la vista se ejecuta
    con los permisos de su owner y el RLS de `stock_movimientos` NO se aplica — un tenant
    terminaría viendo el stock de otro.
    """
    op.execute(
        """
        create view stock with (security_invoker = true) as
        select org_id,
               articulo_id,
               deposito_id,
               sum(cantidad) as cantidad
        from stock_movimientos
        group by org_id, articulo_id, deposito_id;
        """
    )
    op.execute(f"grant select on stock to {APP_ROLE};")


def _blindar_kardex() -> None:
    """Append-only de verdad: la base lo hace cumplir, no la buena voluntad del código.

    Un UPDATE o DELETE sobre el kardex rompe el histórico y hace que el stock calculado
    deje de reflejar lo que realmente pasó. Un error se corrige con un movimiento de
    ajuste que lo compensa, como un contra-asiento. Nunca borrando el pasado.
    """
    op.execute(f"revoke update, delete on stock_movimientos from {APP_ROLE};")

    op.execute(
        """
        create or replace function kardex_append_only() returns trigger as $$
        begin
            raise exception
                'stock_movimientos es append-only: corregí con un movimiento de ajuste';
        end;
        $$ language plpgsql;
        """
    )
    op.execute(
        """
        create trigger trg_kardex_append_only
        before update or delete on stock_movimientos
        for each row execute function kardex_append_only();
        """
    )


def _aplicar_rls() -> None:
    """Aislamiento multi-tenant. La barrera vive en la BASE, no en el código de la app.

    Aunque un bug del dominio olvide filtrar por org, o el LLM del asistente genere un
    SELECT de más, Postgres no deja cruzar de tenant. Es la red de seguridad de todo el
    producto.

    `force row level security` porque el owner de la tabla está exento de RLS por defecto:
    sin esto, cualquier cosa que corriera como owner vería todos los tenants.

    `with check` es tan importante como `using`: `using` controla qué filas VES,
    `with check` controla qué filas podés ESCRIBIR. Sin él, un tenant podría insertar
    filas dentro de otro.
    """
    for tabla in TABLAS_TENANT_0001:
        op.execute(f"alter table {tabla} enable row level security;")
        op.execute(f"alter table {tabla} force row level security;")
        op.execute(
            f"""
            create policy tenant_isolation on {tabla}
                using      (org_id = current_setting('app.current_org_id', true)::uuid)
                with check (org_id = current_setting('app.current_org_id', true)::uuid);
            """
        )

    # `miembros` es la excepción: se lee ANTES de saber el org_id (es la tabla que lo
    # resuelve). Filtra por usuario. El usuario solo ve sus propias membresías, así que
    # no puede descubrir ni reclamar la org de otro.
    op.execute("alter table miembros enable row level security;")
    op.execute("alter table miembros force row level security;")
    op.execute(
        """
        create policy propia_membresia on miembros
            for select
            using (user_id = current_setting('app.current_user_id', true)::uuid);
        """
    )

    # `organizaciones`: la app solo ve la suya. Sin política de escritura — dar de alta un
    # tenant es una operación administrativa, no algo que haga la app con el rol app_user.
    op.execute("alter table organizaciones enable row level security;")
    op.execute("alter table organizaciones force row level security;")
    op.execute(
        """
        create policy propia_organizacion on organizaciones
            for select
            using (id = current_setting('app.current_org_id', true)::uuid);
        """
    )


def downgrade() -> None:
    op.execute("drop trigger if exists trg_kardex_append_only on stock_movimientos;")
    op.execute("drop function if exists kardex_append_only();")
    op.execute("drop view if exists stock;")

    for tabla in (*TABLAS_TENANT_0001, "miembros", "organizaciones"):
        op.execute(f"drop table if exists {tabla} cascade;")
