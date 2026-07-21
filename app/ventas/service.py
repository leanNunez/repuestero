"""Orquestación de ventas. NO escribe SQL crudo: compone los services de cada módulo.

El dueño de `articulos` es `catalogo`, el de `clientes` es `clientes`, y el ÚNICO camino al
stock es `inventario.registrar_movimiento`. Este módulo los usa; nunca toca sus tablas directo
(mismo criterio que `app/ingesta_visual/service.py`).

Una venta es UNA transacción todo-o-nada: o entran la cabecera, todos los renglones y todos los
movimientos de stock, o no entra nada. No abre sesión ni commitea — recibe la del request y
termina en flush(); el commit lo hace `get_tenant` (app/core/rls.py).
"""

from datetime import date
from decimal import ROUND_HALF_UP, Decimal
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.catalogo import service as catalogo
from app.clientes import service as clientes
from app.inventario import service as inventario
from app.ventas.models import (
    ClienteSaldo,
    Comprobante,
    ComprobanteItem,
    CtaCteMovimiento,
    Numerador,
)
from app.ventas.schemas import VentaCrear

_CENT = Decimal("0.01")


class VentaInvalida(ValueError):
    """Algo del payload no existe o no cierra (cliente/depósito/artículo inexistente, stock
    insuficiente). El router lo traduce a un 422."""


def asignar_numero(session: Session, org_id: UUID, *, tipo: str, pto_venta: int) -> int:
    """Devuelve el próximo número correlativo para (tipo, punto de venta), bajo lock.

    `with_for_update()` sobre la fila del numerador serializa a dos cajas facturando a la vez:
    la segunda espera a que la primera libere la fila. Es el reemplazo del `Max(Numero)+1` del
    legacy, que con dos cajas duplicaba el número. Corre DENTRO de la transacción de la venta.

    En la PRIMERÍSIMA venta de un (tipo, pto_venta) la fila no existe: se crea con `ultimo=0`.
    Dos transacciones creándola a la vez es una carrera rarísima que atrapa el unique
    `uq_numeradores_org_tipo_pv` (una gana, la otra se lleva un IntegrityError y reintenta).
    """
    fila = session.scalar(
        select(Numerador)
        .where(
            Numerador.org_id == org_id,
            Numerador.tipo == tipo,
            Numerador.pto_venta == pto_venta,
        )
        .with_for_update()
    )
    if fila is None:
        fila = Numerador(org_id=org_id, tipo=tipo, pto_venta=pto_venta, ultimo=0)
        session.add(fila)
        session.flush()

    fila.ultimo += 1
    session.flush()
    return fila.ultimo


def _stock_disponible(
    session: Session, org_id: UUID, *, articulo_id: int, deposito_id: int
) -> Decimal:
    """Stock actual del artículo en ESE depósito, leído de la vista (nunca un número guardado)."""
    for fila in inventario.stock_de_articulo(session, org_id, articulo_id):
        if fila.deposito_id == deposito_id:
            return fila.cantidad
    return Decimal("0")


def crear_venta(
    session: Session,
    org_id: UUID,
    *,
    datos: VentaCrear,
    usuario_id: UUID | None = None,
    fecha: date | None = None,
) -> Comprobante:
    """Emite un comprobante de venta, descuenta el stock e imputa a la cuenta corriente.

    El orden NO es cosmético: PRIMERO se resuelve y valida todo (cliente, depósito, artículos,
    stock) sin escribir una sola fila. Recién cuando todo cierra se asigna el número y se
    escribe. Así un stock insuficiente en el último renglón no deja un comprobante a medias.

    `fecha` es opcional: en la operación normal se omite y la base la pone en `current_date`.
    El seed la usa para fechar ventas históricas — va en el INSERT porque el comprobante es
    append-only y no se puede corregir después.
    """
    cliente = clientes.obtener_cliente(session, org_id, datos.cliente_codigo)
    if cliente is None:
        raise VentaInvalida(f"No existe el cliente {datos.cliente_codigo!r} en tu organización.")

    deposito = inventario.obtener_deposito(session, org_id, datos.deposito_codigo)
    if deposito is None:
        raise VentaInvalida(f"No existe el depósito {datos.deposito_codigo!r} en tu organización.")

    # Resolver + validar TODO antes de escribir. Cada tupla ya trae el IVA y los importes
    # calculados y congelados.
    resueltos: list[tuple] = []
    for renglon in datos.renglones:
        articulo = catalogo.obtener_articulo(session, org_id, renglon.articulo_codigo)
        if articulo is None:
            raise VentaInvalida(
                f"No existe el artículo {renglon.articulo_codigo!r} en tu organización."
            )

        disponible = _stock_disponible(
            session, org_id, articulo_id=articulo.id, deposito_id=deposito.id
        )
        if disponible < renglon.cantidad:
            raise VentaInvalida(
                f"Stock insuficiente de {articulo.codigo}: hay {disponible}, "
                f"se piden {renglon.cantidad}."
            )

        alicuota = (
            renglon.alicuota_iva if renglon.alicuota_iva is not None else articulo.alicuota_iva
        )
        base = (renglon.cantidad * renglon.precio_unitario).quantize(_CENT, ROUND_HALF_UP)
        importe_iva = (base * alicuota / Decimal(100)).quantize(_CENT, ROUND_HALF_UP)
        resueltos.append((articulo, renglon, alicuota, base, importe_iva))

    neto = sum((base for _a, _r, _al, base, _iv in resueltos), Decimal("0"))
    iva = sum((importe_iva for _a, _r, _al, _b, importe_iva in resueltos), Decimal("0"))

    numero = asignar_numero(session, org_id, tipo=datos.tipo, pto_venta=datos.pto_venta)

    comprobante = Comprobante(
        org_id=org_id,
        cliente_id=cliente.id,
        deposito_id=deposito.id,
        tipo=datos.tipo,
        pto_venta=datos.pto_venta,
        numero=numero,
        condicion=datos.condicion,
        neto=neto,
        iva=iva,
        total=neto + iva,
        creado_por=usuario_id,
    )
    if fecha is not None:
        comprobante.fecha = fecha
    session.add(comprobante)
    session.flush()  # ⇐ acá pega el unique si el número ya existe: IntegrityError → 409

    for articulo, renglon, alicuota, base, importe_iva in resueltos:
        session.add(
            ComprobanteItem(
                org_id=org_id,
                comprobante_id=comprobante.id,
                articulo_id=articulo.id,
                cantidad=renglon.cantidad,
                precio_unitario=renglon.precio_unitario,
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
            cantidad=-renglon.cantidad,  # negativo: sale
            motivo="venta",
            ref_tipo="comprobante_venta",
            ref_id=comprobante.id,
            usuario_id=usuario_id,
        )

    # Venta a crédito → un Debe en la cuenta corriente. La venta al contado no la toca.
    if datos.condicion == "cta_cte":
        movimiento = CtaCteMovimiento(
            org_id=org_id,
            cliente_id=cliente.id,
            tipo="venta",
            debe=comprobante.total,
            ref_tipo="comprobante",
            ref_id=comprobante.id,
            creado_por=usuario_id,
        )
        if fecha is not None:
            movimiento.fecha = fecha
        session.add(movimiento)

    session.flush()
    return comprobante


def obtener_venta(session: Session, org_id: UUID, comprobante_id: int) -> Comprobante | None:
    return session.scalar(
        select(Comprobante).where(Comprobante.org_id == org_id, Comprobante.id == comprobante_id)
    )


def items_de_venta(session: Session, org_id: UUID, comprobante_id: int) -> list[ComprobanteItem]:
    return list(
        session.scalars(
            select(ComprobanteItem)
            .where(
                ComprobanteItem.org_id == org_id,
                ComprobanteItem.comprobante_id == comprobante_id,
            )
            .order_by(ComprobanteItem.id)
        )
    )


def listar_ventas(
    session: Session, org_id: UUID, *, limite: int = 50, offset: int = 0
) -> tuple[list[Comprobante], int]:
    """Lista paginada + total, más reciente primero. Filtro por org_id explícito además del RLS."""
    total = (
        session.scalar(
            select(func.count()).select_from(Comprobante).where(Comprobante.org_id == org_id)
        )
        or 0
    )
    items = session.scalars(
        select(Comprobante)
        .where(Comprobante.org_id == org_id)
        .order_by(Comprobante.fecha.desc(), Comprobante.id.desc())
        .limit(limite)
        .offset(offset)
    )
    return list(items), total


# --------------------------------------------------------------------------- cuenta corriente


def saldo_cliente(session: Session, org_id: UUID, cliente_id: int) -> Decimal:
    """Saldo actual leído de la VISTA `cliente_saldo` (positivo = el cliente debe).

    Un cliente sin movimientos no tiene fila en la vista: su saldo es 0.
    """
    saldo = session.scalar(
        select(ClienteSaldo.saldo).where(
            ClienteSaldo.org_id == org_id, ClienteSaldo.cliente_id == cliente_id
        )
    )
    return saldo if saldo is not None else Decimal("0")


def registrar_cobranza(
    session: Session,
    org_id: UUID,
    *,
    cliente_codigo: str,
    monto: Decimal,
    usuario_id: UUID | None = None,
) -> CtaCteMovimiento:
    """Imputa un pago del cliente como un Haber en la cuenta corriente. Baja el saldo.

    No abre sesión ni commitea (termina en flush), igual que el resto. El saldo se recalcula
    solo desde la vista: no hay columna que actualizar.
    """
    if monto <= 0:
        raise VentaInvalida("El monto de la cobranza debe ser mayor a cero.")

    cliente = clientes.obtener_cliente(session, org_id, cliente_codigo)
    if cliente is None:
        raise VentaInvalida(f"No existe el cliente {cliente_codigo!r} en tu organización.")

    movimiento = CtaCteMovimiento(
        org_id=org_id,
        cliente_id=cliente.id,
        tipo="cobranza",
        haber=monto,
        creado_por=usuario_id,
    )
    session.add(movimiento)
    session.flush()
    return movimiento
