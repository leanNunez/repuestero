from logging.config import fileConfig

from sqlalchemy import engine_from_config, pool

from alembic import context
from app.core.config import get_settings
from app.core.registry import Base

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

settings = get_settings()

# Alembic corre como OWNER del esquema (crea tablas y políticas). La app corre como
# app_user, que no puede crear nada y está sujeto a RLS. Son dos roles distintos a propósito.
config.set_main_option(
    "sqlalchemy.url",
    settings.migrations_database_url or settings.database_url,
)

target_metadata = Base.metadata


def include_object(obj, name, type_, reflected, compare_to) -> bool:
    """Excluye las vistas del autogenerate.

    `stock` está mapeada como entidad para poder consultarla con el ORM, pero es una VISTA.
    Sin este filtro, Alembic la vería en el metadata y generaría un `create_table("stock")`,
    que además chocaría con la vista real.
    """
    return not (type_ == "table" and obj.info.get("is_view"))


def run_migrations_offline() -> None:
    context.configure(
        url=config.get_main_option("sqlalchemy.url"),
        target_metadata=target_metadata,
        literal_binds=True,
        include_object=include_object,
        compare_type=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            include_object=include_object,
            compare_type=True,
        )
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
