"""CLI de reindexado de embeddings del catálogo.

    python -m app.catalogo.reindex

Genera el embedding de todos los artículos que aún no lo tienen. Se corre una vez después de
importar un seed (o tras un alta masiva). Como el importador, usa MIGRATIONS_DATABASE_URL (el
owner, que no está sujeto a RLS) para ver e indexar los artículos de todos los tenants de una.
"""

import sys

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

import app.core.registry  # noqa: F401  — registra TODOS los modelos (FK articulos→organizaciones)
from app.catalogo.service import reindexar_embeddings
from app.core.config import get_settings


def main(argv: list[str] | None = None) -> int:
    settings = get_settings()
    engine = create_engine(settings.migrations_database_url or settings.database_url)

    print("Cargando modelo y reindexando (la 1ª vez baja ~120MB)…")
    with Session(engine) as session:
        n = reindexar_embeddings(session)
        session.commit()

    print(f"Listo: {n} artículos reindexados.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
