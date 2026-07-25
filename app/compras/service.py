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
from typing import Any
from uuid import UUID

from sqlalchemy import Row, and_, func, join, or_, select
from sqlalchemy.orm import Session, aliased

from app.catalogo import service as catalogo
from app.catalogo.schemas import ArticuloActualizar
from app.compras.models import Compra, CompraItem, ProvCtaCteMovimiento, ProveedorSaldo
from app.compras.schemas import CompraCrear
from app.inventario import service as inventario
from app.proveedores import service as proveedores
from app.proveedores.models import Proveedor

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

#: `ref_tipo` de un ajuste que revierte a otro movimiento; su `ref_id` apunta al original.
REF_REVERSA = "ajuste_de"

#: Qué se puede revertir con un storno. NO está 'compra': ese movimiento ESPEJA un documento de
#: compra, y cancelar su efecto desde el ledger dejaría la compra viva con la cuenta en cero, en
#: silencio. Espejo de `ventas.MOVIMIENTOS_REVERSIBLES`, donde está la explicación larga.
MOVIMIENTOS_REVERSIBLES = frozenset({"pago", "ajuste"})


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


def registrar_ajuste(
    session: Session,
    org_id: UUID,
    *,
    proveedor_id: int,
    motivo: str,
    debe: Decimal | None = None,
    haber: Decimal | None = None,
    revierte_movimiento_id: int | None = None,
    usuario_id: UUID | None = None,
) -> ProvCtaCteMovimiento:
    """Corrige la cuenta corriente del proveedor con una fila NUEVA. El pasado no se toca.

    Espejo exacto de `ventas.registrar_ajuste`, donde está la explicación completa de los dos
    modos (reversa con importe calculado por el service, o ajuste manual) y de por qué el motivo
    es obligatorio. Acá el significado va invertido: un debe sube lo que le debemos.

    No abre sesión ni commitea (termina en flush). El saldo sale solo de la vista.
    """
    motivo = motivo.strip()
    if not motivo:
        raise CompraInvalida("El ajuste necesita un motivo: sin él la corrección no se puede leer.")

    proveedor = proveedores.obtener_proveedor_por_id(session, org_id, proveedor_id)
    if proveedor is None:
        raise CompraInvalida("No existe ese proveedor en tu organización.")

    ref_tipo: str | None = None
    ref_id: int | None = None

    if revierte_movimiento_id is not None:
        if debe is not None or haber is not None:
            raise CompraInvalida(
                "Una reversa no lleva importe: lo calcula el sistema desde el movimiento original."
            )

        # El filtro por `proveedor_id` no es redundante con el de org: sin él se podría revertir el
        # movimiento de OTRO proveedor de la misma organización pasando su id a mano.
        original = session.scalar(
            select(ProvCtaCteMovimiento).where(
                ProvCtaCteMovimiento.org_id == org_id,
                ProvCtaCteMovimiento.id == revierte_movimiento_id,
                ProvCtaCteMovimiento.proveedor_id == proveedor_id,
            )
        )
        if original is None:
            raise CompraInvalida("No existe ese movimiento en la cuenta de este proveedor.")

        if original.tipo not in MOVIMIENTOS_REVERSIBLES:
            raise CompraInvalida(
                f"Un movimiento de tipo {original.tipo!r} no se revierte desde la cuenta "
                "corriente porque refleja un documento de compra."
            )

        # Chequeo previo solo para dar un error legible: la garantía REAL es el índice único
        # parcial de la 0009, porque entre este SELECT y el INSERT entra otra transacción.
        if session.scalar(
            select(ProvCtaCteMovimiento.id).where(
                ProvCtaCteMovimiento.org_id == org_id,
                ProvCtaCteMovimiento.ref_tipo == REF_REVERSA,
                ProvCtaCteMovimiento.ref_id == original.id,
            )
        ):
            raise CompraInvalida("Ese movimiento ya fue revertido con un ajuste.")

        debe, haber = original.haber, original.debe
        ref_tipo, ref_id = REF_REVERSA, original.id
    else:
        importes = [m for m in (debe, haber) if m is not None]
        if not importes:
            raise CompraInvalida("Un ajuste manual lleva un importe en Debe o en Haber.")
        if len(importes) == 2:
            raise CompraInvalida("Un ajuste va en Debe o en Haber, no en los dos a la vez.")
        if importes[0] <= 0:
            raise CompraInvalida("El importe del ajuste debe ser mayor a cero.")

    movimiento = ProvCtaCteMovimiento(
        org_id=org_id,
        proveedor_id=proveedor_id,
        tipo="ajuste",
        debe=debe if debe is not None else Decimal("0"),
        haber=haber if haber is not None else Decimal("0"),
        ref_tipo=ref_tipo,
        ref_id=ref_id,
        motivo=motivo,
        creado_por=usuario_id,
    )
    session.add(movimiento)
    session.flush()
    return movimiento


def listar_cuentas_proveedores(
    session: Session,
    org_id: UUID,
    *,
    buscar: str | None = None,
    solo_con_saldo: bool = True,
    limite: int = 50,
    offset: int = 0,
) -> tuple[list[Row[Any]], int, Decimal]:
    """Cuentas corrientes de proveedores con su saldo: página, total y suma del conjunto filtrado.

    Espejo de `ventas.listar_cuentas_clientes`, incluida la excepción consciente a la regla de
    arriba: esto lee `proveedores` directo porque filtrar, ordenar por saldo y paginar exige que
    el JOIN lo resuelva el motor. Es SOLO lectura.
    """
    saldo = func.coalesce(ProveedorSaldo.saldo, Decimal("0"))

    filtros = [Proveedor.org_id == org_id, Proveedor.activo.is_(True)]
    if buscar:
        patron = f"%{buscar}%"
        filtros.append(or_(Proveedor.razon_social.ilike(patron), Proveedor.codigo.ilike(patron)))
    if solo_con_saldo:
        filtros.append(saldo != 0)

    # LEFT JOIN obligatorio: `proveedor_saldo` es un group by sobre los movimientos, así que un
    # proveedor al que siempre se le pagó al contado NO tiene fila.
    origen = join(
        Proveedor,
        ProveedorSaldo,
        and_(
            ProveedorSaldo.org_id == Proveedor.org_id,
            ProveedorSaldo.proveedor_id == Proveedor.id,
        ),
        isouter=True,
    )

    total, suma = session.execute(
        select(func.count(), func.coalesce(func.sum(saldo), Decimal("0")))
        .select_from(origen)
        .where(*filtros)
    ).one()

    filas = session.execute(
        select(
            Proveedor.id,
            Proveedor.codigo,
            Proveedor.razon_social.label("nombre"),
            saldo.label("saldo"),
        )
        .select_from(origen)
        .where(*filtros)
        # Mayor deuda primero, con desempate explícito: sin él dos cuentas con el mismo saldo
        # pueden bailar entre páginas y aparecer repetidas o desaparecer.
        .order_by(saldo.desc(), Proveedor.razon_social, Proveedor.id)
        .limit(limite)
        .offset(offset)
    ).all()

    return list(filas), total or 0, suma if suma is not None else Decimal("0")


def movimientos_proveedor(
    session: Session, org_id: UUID, proveedor_id: int, *, limite: int = 50, offset: int = 0
) -> tuple[list[Row[Any]], int]:
    """Extracto paginado, más reciente primero, con el saldo acumulado de cada renglón.

    Espejo de `ventas.movimientos_cliente`: el acumulado se calcula acá y nunca en el front,
    que solo ve una página y no puede conocer el acumulado de las anteriores. También trae
    `motivo` y `anulado`, para que el extracto pueda mostrar qué movimiento quedó revertido.
    """
    acumulado = (
        func.sum(ProvCtaCteMovimiento.debe - ProvCtaCteMovimiento.haber)
        .over(
            partition_by=(ProvCtaCteMovimiento.org_id, ProvCtaCteMovimiento.proveedor_id),
            order_by=(ProvCtaCteMovimiento.fecha, ProvCtaCteMovimiento.id),
            # ROWS explícito: el frame RANGE por defecto le daría el mismo acumulado a todos los
            # movimientos de la misma fecha (son peers), y dos remitos el mismo día es normal.
            rows=(None, 0),
        )
        .label("saldo_acumulado")
    )

    # ¿Alguien ya revirtió esta fila? EXISTS correlacionado sobre el MISMO ledger, así que hace
    # falta un alias para distinguir la reversa del movimiento revertido.
    reversa = aliased(ProvCtaCteMovimiento)
    anulado = (
        select(reversa.id)
        .where(
            reversa.org_id == ProvCtaCteMovimiento.org_id,
            reversa.ref_tipo == REF_REVERSA,
            reversa.ref_id == ProvCtaCteMovimiento.id,
        )
        .exists()
        .label("anulado")
    )

    filtros = (
        ProvCtaCteMovimiento.org_id == org_id,
        ProvCtaCteMovimiento.proveedor_id == proveedor_id,
    )

    total = (
        session.scalar(select(func.count()).select_from(ProvCtaCteMovimiento).where(*filtros)) or 0
    )

    # La window en una subquery y el orden de lectura afuera: si mañana se filtra por rango de
    # fechas, el WHERE no puede recortar el ledger ANTES de acumular. El EXISTS va acá adentro por
    # lo mismo: afuera se evaluaría sobre la ventana ya recortada.
    ledger = (
        select(
            ProvCtaCteMovimiento.id,
            ProvCtaCteMovimiento.fecha,
            ProvCtaCteMovimiento.tipo,
            ProvCtaCteMovimiento.debe,
            ProvCtaCteMovimiento.haber,
            ProvCtaCteMovimiento.ref_tipo,
            ProvCtaCteMovimiento.ref_id,
            ProvCtaCteMovimiento.motivo,
            anulado,
            acumulado,
        )
        .where(*filtros)
        .subquery()
    )

    filas = session.execute(
        select(ledger)
        .order_by(ledger.c.fecha.desc(), ledger.c.id.desc())
        .limit(limite)
        .offset(offset)
    ).all()

    return list(filas), total
