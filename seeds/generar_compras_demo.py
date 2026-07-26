"""Genera COMPRAS demo 2026 sobre una org ya importada, espejo de `generar_ventas_demo`.

Existe por un agujero concreto: sin compras, `compras` y `prov_cta_cte_movimientos` quedan en
cero, y **toda la solapa de proveedores está construida pero nunca se vio con datos**. El extracto,
el ajuste, la reversa y el pago se probaron con tests y del lado clientes; del lado proveedores no
había una sola fila que mostrar.

Igual que el de ventas, esto NO puede pasar por un CSV: una compra suma stock, pisa el costo,
repricea las listas de venta y (a crédito) imputa la deuda al proveedor, todo transaccional. Por eso
llama a `compras.service.crear_compra` — la misma puerta que usa la app.

    python -m seeds.generar_compras_demo --org "Casa Demo Repuestero"
    python -m seeds.generar_compras_demo --org-id <uuid> --cantidad 400

Dos decisiones que NO son cosméticas, porque `crear_compra` pisa el costo del artículo y repricea
las listas de venta con el margen de cada una:

1. **Las compras se emiten en orden CRONOLÓGICO.** "Último costo pisa" es último *procesado*, no
   último *fechado*. Sin ordenar, el costo final de un artículo sería el de la compra que la
   casualidad dejó al final —perfectamente una de enero— y ese costo se propagaría a los precios de
   venta de todo el catálogo.
2. **El costo de cada compra se deriva del costo ACTUAL del artículo hacia atrás**, con una curva
   que vale ~1 en la fecha de hoy (ver `_factor_costo`). Así la compra vieja es más barata que la
   nueva —que es lo que pasa en la vida real— y, al terminar en orden cronológico, el catálogo
   queda con el costo que ya tenía en vez de saltar a un número inventado.

A crédito va la MAYORÍA (`_PROP_CTA_CTE`), al revés que en ventas: comprarle a un proveedor en
cuenta corriente es la norma, no la excepción — y es justamente lo que este seed viene a llenar.

Cada compra va en su propio savepoint: si un artículo o un dato no cierra, esa compra se saltea y
el resto sigue. Es data de demo; el objetivo es VOLUMEN realista, no cuadrar un balance.
"""

import argparse
import random
from datetime import date, timedelta
from decimal import ROUND_HALF_UP, Decimal
from uuid import UUID

from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session

from app.compras import service
from app.compras.schemas import CompraCrear, RenglonCompraCrear
from app.core import registry  # noqa: F401 — puebla Base.metadata (FKs a organizaciones, etc.)
from app.core.config import get_settings

SEMILLA = 20260726

_CENT = Decimal("0.01")

#: Proporción de compras a cuenta corriente. Alta a propósito: ver el docstring del módulo.
_PROP_CTA_CTE = 0.65

#: Cuánto más barato estaba el costo a principios de 2026 respecto de hoy. 0.55 = hoy vale ~1.8x
#: lo que valía en enero. Es data de demo, no un índice: solo tiene que ordenar bien y no dar
#: números absurdos.
_COSTO_INICIO_ANIO = Decimal("0.55")


def _fecha_2026(rng: random.Random, hoy: date) -> date:
    """Una fecha entre el 1-ene-2026 y hoy, repartida pareja.

    A diferencia del seed de ventas, acá NO se sesga hacia lo reciente: las compras son eventos
    de reposición, mucho menos frecuentes que las ventas y más parejos en el año."""
    inicio = date(2026, 1, 1)
    dias = (hoy - inicio).days
    if dias <= 0:
        return hoy
    return inicio + timedelta(days=rng.randrange(dias + 1))


def _factor_costo(fecha: date, hoy: date) -> Decimal:
    """Cuánto valía el costo en `fecha`, como fracción del costo de hoy. Vale 1 en `hoy`.

    Lineal entre `_COSTO_INICIO_ANIO` (1-ene-2026) y 1 (hoy). Simple a propósito: lo único que
    tiene que garantizar es que una compra vieja salga más barata que una nueva y que la última
    —la de hoy— deje el costo del artículo donde ya estaba."""
    inicio = date(2026, 1, 1)
    total = (hoy - inicio).days
    if total <= 0:
        return Decimal("1")
    avance = Decimal(max(0, min(total, (fecha - inicio).days))) / Decimal(total)
    return _COSTO_INICIO_ANIO + (Decimal("1") - _COSTO_INICIO_ANIO) * avance


def generar_compras(
    session: Session,
    org_id: UUID,
    *,
    cantidad_objetivo: int = 400,
    rng: random.Random | None = None,
    hoy: date | None = None,
) -> int:
    """Emite hasta `cantidad_objetivo` compras sobre la org. Devuelve cuántas entraron de verdad.

    No commitea: el caller decide (el CLI commitea al final; el test hace rollback)."""
    rng = rng or random.Random(SEMILLA)
    hoy = hoy or date.today()

    proveedores = session.execute(
        text("select codigo from proveedores where org_id = :o and activo order by codigo"),
        {"o": org_id},
    ).all()
    articulos = session.execute(
        text(
            """
            select codigo, costo
            from articulos
            where org_id = :o and activo and costo > 0
            order by codigo
            """
        ),
        {"o": org_id},
    ).all()
    if not proveedores or not articulos:
        return 0

    # El plan se arma primero con su fecha y se ORDENA por fecha: "último costo pisa" es último
    # procesado, no último fechado. Ver el punto 1 del docstring del módulo.
    plan: list[tuple[date, object]] = []
    for _ in range(cantidad_objetivo):
        plan.append((_fecha_2026(rng, hoy), rng.choice(proveedores)))
    plan.sort(key=lambda par: par[0])

    #: Correlativo de factura POR proveedor: el unique es (org, proveedor, numero_comprobante).
    siguiente: dict[str, int] = {}

    creadas = 0
    for fecha, prov in plan:
        # Una compra es una reposición: más renglones y más cantidad que una venta de mostrador.
        renglones = []
        for art in rng.sample(articulos, k=min(len(articulos), rng.randint(2, 8))):
            costo_hoy = Decimal(art.costo)
            costo = (costo_hoy * _factor_costo(fecha, hoy)).quantize(_CENT, ROUND_HALF_UP)
            renglones.append(
                RenglonCompraCrear(
                    articulo_codigo=art.codigo,
                    cantidad=Decimal(rng.randint(5, 40)),
                    costo_unitario=max(costo, _CENT),
                )
            )

        siguiente[prov.codigo] = siguiente.get(prov.codigo, 0) + 1
        datos = CompraCrear(
            proveedor_codigo=prov.codigo,
            deposito_codigo="CEN",
            numero_comprobante=f"0001-{siguiente[prov.codigo]:08d}",
            condicion="cta_cte" if rng.random() < _PROP_CTA_CTE else "contado",
            renglones=renglones,
        )

        sp = session.begin_nested()
        try:
            service.crear_compra(session, org_id, datos=datos, fecha=fecha)
            sp.commit()
            creadas += 1
        except service.CompraInvalida:
            sp.rollback()  # dato que no cierra: se saltea, el resto sigue

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
    parser = argparse.ArgumentParser(
        description="Genera compras demo 2026 sobre una org importada."
    )
    grupo = parser.add_mutually_exclusive_group(required=True)
    grupo.add_argument("--org", help="Nombre de la organización (ej: 'Casa Demo Repuestero').")
    grupo.add_argument("--org-id", help="UUID de la organización.")
    parser.add_argument("--cantidad", type=int, default=400, help="Compras objetivo (default 400).")
    args = parser.parse_args()

    # Owner: bypassa RLS para sembrar sobre cualquier org (mismo criterio que el importador).
    engine = create_engine(get_settings().migrations_database_url)
    with Session(engine) as session:
        org = _resolver_org(session, nombre=args.org, org_id=args.org_id)
        creadas = generar_compras(session, org, cantidad_objetivo=args.cantidad)
        session.commit()
    engine.dispose()
    print(f"Listo: {creadas} compras generadas para la org {org}.")


if __name__ == "__main__":
    main()
