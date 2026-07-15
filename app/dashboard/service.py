"""Dashboards de Fase 1: reposición inteligente y guardián de márgenes.

Solo LECTURA sobre datos que ya existen (Articulo, la VISTA Stock, ArticuloPrecio). Como el resto
del dominio, los filtros por org_id son explícitos aunque RLS ya los garantice: dos barreras, una en
el código y otra en el motor.
"""

from decimal import Decimal
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.catalogo.models import Articulo, ArticuloPrecio
from app.inventario.models import Stock

#: Umbral por defecto del guardián de márgenes (%). Por debajo, se marca como bajo.
UMBRAL_MARGEN_DEFAULT = Decimal("20")


def _stock_por_articulo(org_id: UUID):
    """Subconsulta: stock total por artículo (SUM de la vista Stock, que ya es SUM de movimientos)."""
    return (
        select(
            Stock.articulo_id.label("articulo_id"),
            func.coalesce(func.sum(Stock.cantidad), 0).label("stock"),
        )
        .where(Stock.org_id == org_id)
        .group_by(Stock.articulo_id)
        .subquery()
    )


def reposicion(session: Session, org_id: UUID) -> list[dict]:
    """Artículos activos con punto de pedido definido cuyo stock cayó a/por debajo de ese punto."""
    sub = _stock_por_articulo(org_id)
    stock = func.coalesce(sub.c.stock, 0)
    stmt = (
        select(
            Articulo.codigo,
            Articulo.detalle,
            Articulo.marca,
            stock.label("stock"),
            Articulo.punto_pedido,
        )
        .outerjoin(sub, sub.c.articulo_id == Articulo.id)
        .where(
            Articulo.org_id == org_id,
            Articulo.activo.is_(True),
            Articulo.punto_pedido > 0,
            stock <= Articulo.punto_pedido,
        )
        .order_by((Articulo.punto_pedido - stock).desc())
    )
    return [
        {
            "codigo": r.codigo,
            "detalle": r.detalle,
            "marca": r.marca,
            "stock": r.stock,
            "punto_pedido": r.punto_pedido,
            "faltante": r.punto_pedido - r.stock,
        }
        for r in session.execute(stmt)
    ]


def margenes(
    session: Session, org_id: UUID, umbral: Decimal = UMBRAL_MARGEN_DEFAULT
) -> list[dict]:
    """Margen real por artículo, tomando el PEOR margen entre sus listas (la venta más flaca).

    Como el margen crece con el precio (margen = 1 - costo/precio), el mínimo margen coincide con
    el mínimo precio: por eso `min(precio)` y `min(margen)` son la misma fila.
    """
    margen_expr = (
        (ArticuloPrecio.precio - Articulo.costo)
        / func.nullif(ArticuloPrecio.precio, 0)
        * 100
    )
    stmt = (
        select(
            Articulo.codigo,
            Articulo.detalle,
            Articulo.marca,
            Articulo.costo,
            func.min(ArticuloPrecio.precio).label("precio"),
            func.min(margen_expr).label("margen"),
        )
        .join(ArticuloPrecio, ArticuloPrecio.articulo_id == Articulo.id)
        .where(
            Articulo.org_id == org_id,
            Articulo.activo.is_(True),
            ArticuloPrecio.org_id == org_id,
        )
        .group_by(Articulo.id, Articulo.codigo, Articulo.detalle, Articulo.marca, Articulo.costo)
        .order_by(func.min(margen_expr).asc())
    )
    filas = []
    for r in session.execute(stmt):
        margen = Decimal(r.margen).quantize(Decimal("0.01")) if r.margen is not None else Decimal("0")
        filas.append(
            {
                "codigo": r.codigo,
                "detalle": r.detalle,
                "marca": r.marca,
                "costo": r.costo,
                "precio": r.precio,
                "margen": margen,
                "bajo": margen < umbral,
            }
        )
    return filas


def resumen(session: Session, org_id: UUID) -> dict:
    """KPIs de cabecera del dashboard."""
    total = session.scalar(
        select(func.count())
        .select_from(Articulo)
        .where(Articulo.org_id == org_id, Articulo.activo.is_(True))
    )
    valor_stock = session.scalar(
        select(func.coalesce(func.sum(Stock.cantidad * Articulo.costo), 0))
        .select_from(Stock)
        .join(Articulo, Articulo.id == Stock.articulo_id)
        .where(Stock.org_id == org_id)
    )
    return {
        "total_articulos": total or 0,
        "bajo_punto_pedido": len(reposicion(session, org_id)),
        "margen_bajo": sum(1 for m in margenes(session, org_id) if m["bajo"]),
        "valor_stock": valor_stock or Decimal("0"),
    }
