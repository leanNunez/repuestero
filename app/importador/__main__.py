"""CLI del importador.

    python -m app.importador --org <uuid> --source seeds/demo
    python -m app.importador --crear-org "Casa de Repuestos Demo" --source seeds/demo

El importador NO corre como app_user: crear la organización y cargar el tenant inicial son
operaciones administrativas. Usa MIGRATIONS_DATABASE_URL (el owner), que no está sujeto a
RLS. La app en runtime sí lo está — que es lo que importa.
"""

import argparse
import sys
from pathlib import Path
from uuid import UUID, uuid4

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.models import Miembro, Organizacion
from app.importador.loader import importar
from app.importador.readers.csv_reader import CsvSourceReader


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="app.importador")
    parser.add_argument("--source", type=Path, default=Path("seeds/demo"))
    parser.add_argument("--org", type=UUID, help="UUID de una organización existente")
    parser.add_argument("--crear-org", type=str, help="Nombre de una organización nueva")
    parser.add_argument(
        "--miembro",
        type=UUID,
        help="user_id de Supabase Auth a dar de alta como miembro de la org",
    )
    args = parser.parse_args(argv)

    if not args.org and not args.crear_org:
        parser.error("Indicá --org <uuid> o --crear-org <nombre>")

    settings = get_settings()
    engine = create_engine(settings.migrations_database_url or settings.database_url)

    with Session(engine) as session:
        if args.crear_org:
            org = Organizacion(id=uuid4(), nombre=args.crear_org)
            session.add(org)
            session.flush()
            org_id = org.id
            print(f"Organización creada: {org_id}  ({args.crear_org})")
        else:
            org_id = args.org

        if args.miembro:
            session.add(Miembro(org_id=org_id, user_id=args.miembro, rol="admin"))
            print(f"Miembro dado de alta: {args.miembro} → admin")

        resumen = importar(session, org_id, CsvSourceReader(args.source))
        session.commit()

    print(f"\nImportado en org {org_id} desde {args.source}:")
    print(resumen)
    return 0


if __name__ == "__main__":
    sys.exit(main())
