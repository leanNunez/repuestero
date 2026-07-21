"""Genera VENTAS demo 2026 sobre una org ya importada, para que Repu tenga qué responder.

A diferencia de `generar_demo.py` (que escribe CSVs para el importador), esto NO puede pasar por
un CSV: un comprobante no es una fila que se inserta y ya. Emitirlo bien exige numeración con
lock, descuento de stock y (si es a crédito) imputación a cuenta corriente, todo transaccional.
Por eso el seed llama a `ventas.service.crear_venta` — la misma puerta que usa la app.

La distribución imita un negocio real: bastantes clientes SIN comprar, muchos con una o dos
compras, y unos pocos FRECUENTES. Las fechas se reparten a lo largo de 2026 con un puñado en el
día de hoy, para que "ventas de hoy", "clientes frecuentes" y "última compra" den algo jugoso.

    python -m seeds.generar_ventas_demo --org "Casa Demo Repuestero"
    python -m seeds.generar_ventas_demo --org-id <uuid> --cantidad 1500

Cada venta va en su propio savepoint: si un artículo se quedó sin stock, esa venta se saltea y el
resto sigue. Es data de demo; el objetivo es VOLUMEN realista, no cuadrar un balance.
"""

import argparse
import random
from datetime import date, timedelta
from decimal import Decimal
from uuid import UUID

from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session

from app.core import registry  # noqa: F401 — puebla Base.metadata (FKs a organizaciones, etc.)
from app.core.config import get_settings
from app.ventas import service
from app.ventas.schemas import RenglonVentaCrear, VentaCrear

SEMILLA = 20260721


def _fecha_2026(rng: random.Random, hoy: date) -> date:
    """Una fecha entre el 1-ene-2026 y hoy, sesgada hacia lo reciente (los últimos meses pesan más)."""
    inicio = date(2026, 1, 1)
    dias = (hoy - inicio).days
    if dias <= 0:
        return hoy
    # random**0.6 empuja la distribución hacia 1 → fechas más cercanas a hoy.
    return inicio + timedelta(days=int(dias * rng.random() ** 0.6))


def generar_ventas(
    session: Session,
    org_id: UUID,
    *,
    cantidad_objetivo: int = 1500,
    rng: random.Random | None = None,
    hoy: date | None = None,
) -> int:
    """Emite hasta `cantidad_objetivo` ventas sobre la org. Devuelve cuántas entraron de verdad.

    No commitea: el caller decide (el CLI commitea al final; el test hace rollback)."""
    rng = rng or random.Random(SEMILLA)
    hoy = hoy or date.today()

    clientes = session.execute(
        text(
            "select codigo, cond_fiscal from clientes where org_id = :o and activo order by codigo"
        ),
        {"o": org_id},
    ).all()
    articulos = session.execute(
        text(
            """
            select a.codigo,
                   coalesce(p.precio, round(a.costo * 1.6, 2)) as precio
            from articulos a
            left join listas_precio l on l.org_id = a.org_id and l.codigo = 'MOST'
            left join articulo_precios p on p.articulo_id = a.id and p.lista_id = l.id
            where a.org_id = :o and a.activo
            order by a.codigo
            """
        ),
        {"o": org_id},
    ).all()
    if not clientes or not articulos:
        return 0

    # ~45% de los clientes compran. A unos pocos se les da MUCHO peso (los frecuentes).
    compradores = [c for c in clientes if rng.random() < 0.45]
    rng.shuffle(compradores)
    plan: list = []
    for i, cli in enumerate(compradores):
        # Los primeros ~4% son los FRECUENTES: muchas compras. El resto, una o dos.
        n = rng.randint(8, 20) if i < max(1, len(compradores) // 25) else rng.randint(1, 3)
        plan.extend([cli] * n)
    rng.shuffle(plan)

    creadas = 0
    for cli in plan:
        if creadas >= cantidad_objetivo:
            break
        # Un puñado de ventas caen HOY, para "ventas de hoy". El resto, repartidas en 2026.
        fecha = hoy if rng.random() < 0.03 else _fecha_2026(rng, hoy)
        renglones = [
            RenglonVentaCrear(
                articulo_codigo=art.codigo,
                cantidad=Decimal(rng.randint(1, 2)),
                precio_unitario=Decimal(art.precio),
            )
            for art in rng.sample(articulos, k=min(len(articulos), rng.randint(1, 3)))
        ]
        # Consumidor final siempre contado; el resto, mezcla con sesgo a contado.
        condicion = (
            "contado" if cli.cond_fiscal == "CONSUMIDOR_FINAL" or rng.random() < 0.6 else "cta_cte"
        )
        datos = VentaCrear(
            cliente_codigo=cli.codigo,
            deposito_codigo="CEN",
            condicion=condicion,
            renglones=renglones,
        )

        sp = session.begin_nested()
        try:
            service.crear_venta(session, org_id, datos=datos, fecha=fecha)
            sp.commit()
            creadas += 1
        except service.VentaInvalida:
            sp.rollback()  # sin stock (u otro dato): se saltea, el resto sigue

    return creadas


def _resolver_org(session: Session, *, nombre: str | None, org_id: str | None) -> UUID:
    if org_id:
        return UUID(org_id)
    fila = session.execute(
        text("select id from organizaciones where nombre = :n"), {"n": nombre}
    ).scalar_one_or_none()
    if fila is None:
        raise SystemExit(f"No encontré la organización {nombre!r}.")
    return fila


def main() -> None:
    parser = argparse.ArgumentParser(description="Genera ventas demo 2026 sobre una org importada.")
    grupo = parser.add_mutually_exclusive_group(required=True)
    grupo.add_argument("--org", help="Nombre de la organización (ej: 'Casa Demo Repuestero').")
    grupo.add_argument("--org-id", help="UUID de la organización.")
    parser.add_argument(
        "--cantidad", type=int, default=1500, help="Ventas objetivo (default 1500)."
    )
    args = parser.parse_args()

    # Owner: bypassa RLS para sembrar sobre cualquier org (mismo criterio que el importador).
    engine = create_engine(get_settings().migrations_database_url)
    with Session(engine) as session:
        org = _resolver_org(session, nombre=args.org, org_id=args.org_id)
        creadas = generar_ventas(session, org, cantidad_objetivo=args.cantidad)
        session.commit()
    engine.dispose()
    print(f"Listo: {creadas} ventas generadas para la org {org}.")


if __name__ == "__main__":
    main()
