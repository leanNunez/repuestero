"""Orquestación de compras. NO escribe SQL crudo: compone los services de cada módulo.

El dueño de `articulos`/precios es `catalogo`, el de `proveedores` es `proveedores`, y el ÚNICO
camino al stock es `inventario.registrar_movimiento`. Este módulo los usa; nunca toca sus tablas
directo (mismo criterio que `app/ventas/service.py`).

Una compra es UNA transacción todo-o-nada: o entran la cabecera, todos los renglones, todos los
movimientos de stock y la actualización de costos, o no entra nada. No abre sesión ni commitea —
recibe la del request y termina en flush(); el commit lo hace `get_tenant` (app/core/rls.py).
"""

from datetime import date
from decimal import ROUND_HALF_UP, Decimal
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.catalogo import service as catalogo
from app.catalogo.schemas import ArticuloActualizar
from app.compras.models import Compra, CompraItem, ProvCtaCteMovimiento, ProveedorSaldo
from app.compras.schemas import CompraCrear
from app.inventario import service as inventario
from app.proveedores import service as proveedores

_CENT = Decimal("0.01")


class CompraInvalida(ValueError):
    """Algo del payload no existe o no cierra (proveedor/depósito/artículo inexistente). El router
    lo traduce a un 422."""


def crear_compra(
    session: Session,
    org_id: UUID,
    *,
    datos: CompraCrear,
    usuario_id: UUID | None = None,
    fecha: date | None = None,
) -> Compra:
    """Registra una compra: suma stock, actualiza el costo (último costo pisa), repricea las listas
    de venta y, si es a crédito, imputa la deuda a la cuenta corriente del proveedor.

    El orden NO es cosmético: PRIMERO se resuelve y valida todo (proveedor, depósito, artículos)
    sin escribir una sola fila. Recién cuando todo cierra se escribe la cabecera y se procesan los
    renglones. `fecha` es opcional: el seed la usa para compras históricas (la compra es append-only).
    """
    proveedor = proveedores.obtener_proveedor(session, org_id, datos.proveedor_codigo)
    if proveedor is None:
        raise CompraInvalida(
            f"No existe el proveedor {datos.proveedor_codigo!r} en tu organización."
        )

    deposito = inventario.obtener_deposito(session, org_id, datos.deposito_codigo)
    if deposito is None:
        raise CompraInvalida(f"No existe el depósito {datos.deposito_codigo!r} en tu organización.")

    # Resolver + validar TODO antes de escribir. Cada tupla trae el IVA y los importes congelados.
    resueltos: list[tuple] = []
    for renglon in datos.renglones:
        articulo = catalogo.obtener_articulo(session, org_id, renglon.articulo_codigo)
        if articulo is None:
            raise CompraInvalida(
                f"No existe el artículo {renglon.articulo_codigo!r} en tu organización."
            )
        alicuota = (
            renglon.alicuota_iva if renglon.alicuota_iva is not None else articulo.alicuota_iva
        )
        base = (renglon.cantidad * renglon.costo_unitario).quantize(_CENT, ROUND_HALF_UP)
        importe_iva = (base * alicuota / Decimal(100)).quantize(_CENT, ROUND_HALF_UP)
        resueltos.append((articulo, renglon, alicuota, base, importe_iva))

    neto = sum((base for _a, _r, _al, base, _iv in resueltos), Decimal("0"))
    iva = sum((importe_iva for _a, _r, _al, _b, importe_iva in resueltos), Decimal("0"))

    compra = Compra(
        org_id=org_id,
        proveedor_id=proveedor.id,
        deposito_id=deposito.id,
        numero_comprobante=datos.numero_comprobante,
        condicion=datos.condicion,
        neto=neto,
        iva=iva,
        total=neto + iva,
        creado_por=usuario_id,
    )
    if fecha is not None:
        compra.fecha = fecha
    session.add(compra)
    session.flush()  # ⇐ acá pega el unique si la factura ya se cargó: IntegrityError → 409

    for articulo, renglon, alicuota, base, importe_iva in resueltos:
        session.add(
            CompraItem(
                org_id=org_id,
                compra_id=compra.id,
                articulo_id=articulo.id,
                cantidad=renglon.cantidad,
                costo_unitario=renglon.costo_unitario,
                alicuota_iva=alicuota,
                importe_iva=importe_iva,
                total_renglon=base + importe_iva,
            )
        )
        inventario.registrar_movimiento(
            session,
            org_id,
            articulo_id=articulo.id,
            deposito_id=deposito.id,
            cantidad=renglon.cantidad,  # positivo: entra
            motivo="compra",
            ref_tipo="compra",
            ref_id=compra.id,
            usuario_id=usuario_id,
        )
        # Último costo pisa, y los precios de venta se repricean con el margen de cada lista.
        catalogo.actualizar_articulo(
            session,
            org_id,
            articulo=articulo,
            datos=ArticuloActualizar(costo=renglon.costo_unitario),
        )
        catalogo.recalcular_precios_por_costo(
            session, org_id, articulo_id=articulo.id, costo=renglon.costo_unitario
        )
        proveedores.upsert_vinculo_articulo(
            session,
            org_id,
            articulo_id=articulo.id,
            proveedor_id=proveedor.id,
            costo=renglon.costo_unitario,
        )

    # Compra a crédito → un Debe en la cuenta corriente del proveedor (le debemos). La de contado no.
    if datos.condicion == "cta_cte":
        movimiento = ProvCtaCteMovimiento(
            org_id=org_id,
            proveedor_id=proveedor.id,
            tipo="compra",
            debe=compra.total,
            ref_tipo="compra",
            ref_id=compra.id,
            creado_por=usuario_id,
        )
        if fecha is not None:
            movimiento.fecha = fecha
        session.add(movimiento)

    session.flush()
    return compra


def obtener_compra(session: Session, org_id: UUID, compra_id: int) -> Compra | None:
    return session.scalar(select(Compra).where(Compra.org_id == org_id, Compra.id == compra_id))


def items_de_compra(session: Session, org_id: UUID, compra_id: int) -> list[CompraItem]:
    return list(
        session.scalars(
            select(CompraItem)
            .where(CompraItem.org_id == org_id, CompraItem.compra_id == compra_id)
            .order_by(CompraItem.id)
        )
    )


def listar_compras(
    session: Session, org_id: UUID, *, limite: int = 50, offset: int = 0
) -> tuple[list[Compra], int]:
    """Lista paginada + total, más reciente primero. Filtro por org_id explícito además del RLS."""
    total = (
        session.scalar(select(func.count()).select_from(Compra).where(Compra.org_id == org_id)) or 0
    )
    items = session.scalars(
        select(Compra)
        .where(Compra.org_id == org_id)
        .order_by(Compra.fecha.desc(), Compra.id.desc())
        .limit(limite)
        .offset(offset)
    )
    return list(items), total


# --------------------------------------------------------------------------- cuenta corriente


def saldo_proveedor(session: Session, org_id: UUID, proveedor_id: int) -> Decimal:
    """Saldo actual leído de la VISTA `proveedor_saldo` (positivo = le debemos).

    Un proveedor sin movimientos no tiene fila en la vista: su saldo es 0.
    """
    saldo = session.scalar(
        select(ProveedorSaldo.saldo).where(
            ProveedorSaldo.org_id == org_id, ProveedorSaldo.proveedor_id == proveedor_id
        )
    )
    return saldo if saldo is not None else Decimal("0")


def registrar_pago(
    session: Session,
    org_id: UUID,
    *,
    proveedor_codigo: str,
    monto: Decimal,
    usuario_id: UUID | None = None,
) -> ProvCtaCteMovimiento:
    """Imputa un pago al proveedor como un Haber en su cuenta corriente. Baja lo que le debemos.

    No abre sesión ni commitea (termina en flush). El saldo se recalcula solo desde la vista.
    """
    if monto <= 0:
        raise CompraInvalida("El monto del pago debe ser mayor a cero.")

    proveedor = proveedores.obtener_proveedor(session, org_id, proveedor_codigo)
    if proveedor is None:
        raise CompraInvalida(f"No existe el proveedor {proveedor_codigo!r} en tu organización.")

    movimiento = ProvCtaCteMovimiento(
        org_id=org_id,
        proveedor_id=proveedor.id,
        tipo="pago",
        haber=monto,
        creado_por=usuario_id,
    )
    session.add(movimiento)
    session.flush()
    return movimiento
