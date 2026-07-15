"""Búsqueda híbrida: pgvector + full-text español + trigram

Agrega a `articulos` lo necesario para buscar por SIGNIFICADO (embeddings) y por TEXTO
(full-text + tolerancia a typos), que después se fusionan por RRF en el service. Hoy el
catálogo solo tiene ILIKE: "algo para filtrar el aceite" no encuentra el "FILTRO DE ACEITE".

Revision ID: 0002
Revises: 0001
Create Date: 2026-07-14
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0002"
down_revision: str | None = "0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# 384 = dimensión de paraphrase-multilingual-MiniLM-L12-v2 (el modelo de fastembed).
DIM = 384


def upgrade() -> None:
    # `vector` para similitud semántica; `pg_trgm` para el matcheo difuso tolerante a typos.
    # La imagen pgvector/pgvector:pg16 trae ambas; solo hay que habilitarlas.
    op.execute("create extension if not exists vector;")
    op.execute("create extension if not exists pg_trgm;")

    # Embedding del artículo. Nullable: lo llena el reindex batch (no en el hot path de insert,
    # para no cargar el modelo de 120MB en cada proceso que da de alta un artículo).
    op.execute(f"alter table articulos add column embedding vector({DIM});")

    # Columna FTS GENERADA: Postgres la mantiene en sync sola en cada insert/update. Cero
    # mantenimiento y nunca se desincroniza del dato — misma filosofía que el stock como vista.
    op.execute(
        """
        alter table articulos add column busqueda tsvector
            generated always as (
                to_tsvector(
                    'spanish',
                    coalesce(detalle, '') || ' ' || coalesce(marca, '') || ' ' ||
                    coalesce(rubro, '') || ' ' || coalesce(codigo, '')
                )
            ) stored;
        """
    )

    # Índices de las tres vías de búsqueda.
    op.execute("create index ix_articulos_busqueda on articulos using gin (busqueda);")
    op.execute(
        "create index ix_articulos_detalle_trgm on articulos using gin (detalle gin_trgm_ops);"
    )
    # HNSW: sin fase de entrenamiento (a diferencia de ivfflat) y buena latencia para el volumen
    # de un local (~miles de artículos). vector_cosine_ops = distancia coseno (operador <=>).
    op.execute(
        "create index ix_articulos_embedding_hnsw on articulos "
        "using hnsw (embedding vector_cosine_ops);"
    )


def downgrade() -> None:
    op.execute("drop index if exists ix_articulos_embedding_hnsw;")
    op.execute("drop index if exists ix_articulos_detalle_trgm;")
    op.execute("drop index if exists ix_articulos_busqueda;")
    op.execute("alter table articulos drop column if exists busqueda;")
    op.execute("alter table articulos drop column if exists embedding;")
    # Las extensiones se dejan: son inocuas y otras tablas podrían usarlas más adelante.
