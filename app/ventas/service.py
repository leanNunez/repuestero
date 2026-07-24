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
from typing import Any, NamedTuple
from uuid import UUID

from sqlalchemy import Row, and_, func, join, or_, select
from sqlalchemy.orm import Session

from app.catalogo import service as catalogo
from app.clientes import service as clientes
from app.clientes.models import Cliente
from app.inventario import service as inventario
from app.ventas.models import (
    ClienteSaldo,
    Comprobante,
    ComprobanteItem,
    CtaCteMovimiento,
    NotaCredito,
    NotaCreditoItem,
    Numerador,
)
from app.ventas.schemas import NotaCreditoCrear, VentaCrear

_CENT = Decimal("0.01")
_LISTA_DEFECTO = "MOST"  # lista Mostrador: el precio de mostrador cuando el cliente no tiene lista


class VentaInvalida(ValueError):
    """Algo del payload no existe o no cierra (cliente/depósito/artículo inexistente, stock
    insuficiente). El router lo traduce a un 422."""


class NotaCreditoInvalida(ValueError):
    """La NC no cierra: la venta no existe, el artículo no está en ella, se acredita más de lo
    vendido, o ya está totalmente acreditada. El router lo traduce a un 422."""


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


def precio_sugerido(
    session: Session,
    org_id: UUID,
    *,
    articulo_codigo: str,
    cliente_codigo: str | None = None,
) -> tuple[Decimal, str] | None:
    """Precio a proponer para un renglón: el de la lista del cliente, o la lista Mostrador.

    Devuelve `(precio, lista_codigo)`, o `None` si el artículo no existe o esa lista no tiene
    precio fijado para él (el mostrador lo tipea a mano). El precio es sugerencia editable: la
    venta lo toma del payload, no de acá.
    """
    articulo = catalogo.obtener_articulo(session, org_id, articulo_codigo)
    if articulo is None:
        return None

    lista = None
    if cliente_codigo:
        cliente = clientes.obtener_cliente(session, org_id, cliente_codigo)
        if cliente is not None and cliente.lista_precio_id is not None:
            lista = catalogo.obtener_lista_precio_por_id(session, org_id, cliente.lista_precio_id)
    if lista is None:
        lista = catalogo.obtener_lista_precio(session, org_id, _LISTA_DEFECTO)
    if lista is None:
        return None

    precio = catalogo.precio_de_articulo(
        session, org_id, articulo_id=articulo.id, lista_id=lista.id
    )
    if precio is None:
        return None
    return precio.precio, lista.codigo


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


def listar_cuentas_clientes(
    session: Session,
    org_id: UUID,
    *,
    buscar: str | None = None,
    solo_con_saldo: bool = True,
    limite: int = 50,
    offset: int = 0,
) -> tuple[list[Row[Any]], int, Decimal]:
    """Cuentas corrientes de clientes con su saldo: página, total y suma del conjunto filtrado.

    Excepción consciente a la regla de arriba ("nunca toca las tablas de otro módulo"): esto lee
    `clientes` directo. Filtrar, ordenar por saldo y paginar exige que el JOIN lo resuelva el
    motor; delegarlo a `clientes.listar_clientes` significaría traer los 900 clientes a memoria
    para ordenarlos en Python. Es SOLO lectura — ninguna escritura a `clientes` pasa por acá.

    El `saldo_total` sale en la misma llamada y no en un endpoint aparte: se calcula con los
    MISMOS filtros que `total`. Partirlo obliga a reconstruir los filtros en dos lugares, que es
    justo donde se cuela el bug de "el total no coincide con lo que muestra la página".
    """
    saldo = func.coalesce(ClienteSaldo.saldo, Decimal("0"))

    filtros = [Cliente.org_id == org_id, Cliente.activo.is_(True)]
    if buscar:
        patron = f"%{buscar}%"
        filtros.append(or_(Cliente.denominacion.ilike(patron), Cliente.codigo.ilike(patron)))
    if solo_con_saldo:
        filtros.append(saldo != 0)

    # LEFT JOIN obligatorio: `cliente_saldo` es un group by sobre los movimientos, así que un
    # cliente que nunca operó a cuenta corriente NO tiene fila. Con INNER JOIN desaparecería.
    origen = join(
        Cliente,
        ClienteSaldo,
        and_(ClienteSaldo.org_id == Cliente.org_id, ClienteSaldo.cliente_id == Cliente.id),
        isouter=True,
    )

    total, suma = session.execute(
        select(func.count(), func.coalesce(func.sum(saldo), Decimal("0")))
        .select_from(origen)
        .where(*filtros)
    ).one()

    filas = session.execute(
        select(
            Cliente.id,
            Cliente.codigo,
            Cliente.denominacion.label("nombre"),
            saldo.label("saldo"),
            Cliente.limite_cta_cte.label("limite"),
        )
        .select_from(origen)
        .where(*filtros)
        # Mayor deuda primero. El desempate por nombre e id no es cosmético: sin él, dos cuentas
        # con el mismo saldo pueden bailar entre páginas y aparecer repetidas o desaparecer.
        .order_by(saldo.desc(), Cliente.denominacion, Cliente.id)
        .limit(limite)
        .offset(offset)
    ).all()

    return list(filas), total or 0, suma if suma is not None else Decimal("0")


def movimientos_cliente(
    session: Session, org_id: UUID, cliente_id: int, *, limite: int = 50, offset: int = 0
) -> tuple[list[Row[Any]], int]:
    """Extracto paginado, más reciente primero, con el saldo acumulado de cada renglón.

    El acumulado se calcula acá y NUNCA en el front: el front recibe una ventana
    [offset, offset+limite) y el acumulado de su primera fila depende de todas las páginas
    anteriores. Calcularlo del lado del cliente exigiría traer el ledger entero, que es
    exactamente lo que la paginación existe para evitar.
    """
    acumulado = (
        func.sum(CtaCteMovimiento.debe - CtaCteMovimiento.haber)
        .over(
            partition_by=(CtaCteMovimiento.org_id, CtaCteMovimiento.cliente_id),
            order_by=(CtaCteMovimiento.fecha, CtaCteMovimiento.id),
            # ROWS explícito. El frame por defecto es RANGE, y en RANGE todas las filas con la
            # misma `fecha` son peers y comparten el acumulado de cierre del día: dos ventas del
            # mismo día —el caso normal en un mostrador— mostrarían el mismo saldo.
            rows=(None, 0),
        )
        .label("saldo_acumulado")
    )

    filtros = (CtaCteMovimiento.org_id == org_id, CtaCteMovimiento.cliente_id == cliente_id)

    total = session.scalar(select(func.count()).select_from(CtaCteMovimiento).where(*filtros)) or 0

    # La window va en una subquery y el orden de lectura afuera. Hoy daría lo mismo en un solo
    # nivel (Postgres evalúa las window functions después del WHERE y antes del LIMIT), pero el
    # día que se filtre por rango de fechas el WHERE recortaría filas ANTES de acumular y el
    # saldo arrancaría de cero en el rango, mal y en silencio.
    ledger = (
        select(
            CtaCteMovimiento.id,
            CtaCteMovimiento.fecha,
            CtaCteMovimiento.tipo,
            CtaCteMovimiento.debe,
            CtaCteMovimiento.haber,
            CtaCteMovimiento.ref_tipo,
            CtaCteMovimiento.ref_id,
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


# --------------------------------------------------------------------------- notas de crédito


class _RenglonVendido(NamedTuple):
    """Lo vendido de un artículo en una venta, agregado. Precio e IVA congelados del original."""

    articulo_id: int
    precio_unitario: Decimal
    alicuota_iva: Decimal
    cantidad_vendida: Decimal


class RenglonAcreditable(NamedTuple):
    """Lo que resta acreditar de un renglón de una venta (para precargar el flujo de NC)."""

    articulo_id: int
    articulo_codigo: str
    descripcion: str
    precio_unitario: Decimal
    alicuota_iva: Decimal
    cantidad_vendida: Decimal
    cantidad_acreditable: Decimal


def _acreditado_por_articulo(
    session: Session, org_id: UUID, comprobante_id: int
) -> dict[int, Decimal]:
    """Cuánto ya se acreditó por artículo, sumando todas las NCs previas de ese comprobante."""
    filas = session.execute(
        select(NotaCreditoItem.articulo_id, func.sum(NotaCreditoItem.cantidad))
        .join(NotaCredito, NotaCredito.id == NotaCreditoItem.nota_credito_id)
        .where(
            NotaCredito.org_id == org_id,
            NotaCredito.ref_comprobante_id == comprobante_id,
        )
        .group_by(NotaCreditoItem.articulo_id)
    )
    return {articulo_id: cantidad for articulo_id, cantidad in filas}


def _vendido_por_articulo(
    session: Session, org_id: UUID, comprobante_id: int
) -> dict[int, _RenglonVendido]:
    """Lo vendido por artículo en una venta, agregado. Si un artículo aparece en varios renglones
    se suman las cantidades y se toma el precio/IVA del primero (el mostrador arma un renglón por
    artículo; el caso repetido es defensivo)."""
    vendido: dict[int, _RenglonVendido] = {}
    for item in items_de_venta(session, org_id, comprobante_id):
        actual = vendido.get(item.articulo_id)
        if actual is None:
            vendido[item.articulo_id] = _RenglonVendido(
                articulo_id=item.articulo_id,
                precio_unitario=item.precio_unitario,
                alicuota_iva=item.alicuota_iva,
                cantidad_vendida=item.cantidad,
            )
        else:
            vendido[item.articulo_id] = actual._replace(
                cantidad_vendida=actual.cantidad_vendida + item.cantidad
            )
    return vendido


def renglones_acreditables(
    session: Session, org_id: UUID, comprobante_id: int
) -> list[RenglonAcreditable]:
    """Por cada artículo de la venta, cuánto resta acreditar (vendido menos NCs previas).

    Es lo que la UI carga al abrir el flujo de NC: fija los máximos de cada renglón. Un artículo
    ya totalmente acreditado aparece con `cantidad_acreditable = 0`.
    """
    vendido = _vendido_por_articulo(session, org_id, comprobante_id)
    ya = _acreditado_por_articulo(session, org_id, comprobante_id)

    renglones: list[RenglonAcreditable] = []
    for articulo_id, v in vendido.items():
        articulo = catalogo.obtener_articulo_por_id(session, org_id, articulo_id)
        if articulo is None:  # el artículo fue borrado: no debería pasar (FK RESTRICT), defensivo
            continue
        restante = v.cantidad_vendida - ya.get(articulo_id, Decimal("0"))
        renglones.append(
            RenglonAcreditable(
                articulo_id=articulo_id,
                articulo_codigo=articulo.codigo,
                descripcion=articulo.detalle,
                precio_unitario=v.precio_unitario,
                alicuota_iva=v.alicuota_iva,
                cantidad_vendida=v.cantidad_vendida,
                cantidad_acreditable=restante,
            )
        )
    return renglones


def crear_nota_credito(
    session: Session,
    org_id: UUID,
    *,
    datos: NotaCreditoCrear,
    usuario_id: UUID | None = None,
    fecha: date | None = None,
) -> NotaCredito:
    """Emite una NC que revierte (total o parcialmente) una venta: devuelve stock y, si la venta
    era a crédito, baja la deuda con un Haber.

    Igual que la venta, valida TODO antes de escribir: la venta existe, los artículos están en
    ella, y no se acredita más de lo que resta. El precio y el IVA se copian del renglón original
    (no se puede acreditar a otro precio). Numeración propia `tipo='NC'`. No commitea (flush).
    """
    original = obtener_venta(session, org_id, datos.comprobante_id)
    if original is None:
        raise NotaCreditoInvalida(f"No existe la venta {datos.comprobante_id} en tu organización.")

    vendido = _vendido_por_articulo(session, org_id, original.id)
    ya = _acreditado_por_articulo(session, org_id, original.id)

    def _restante(articulo_id: int) -> Decimal:
        return vendido[articulo_id].cantidad_vendida - ya.get(articulo_id, Decimal("0"))

    # (articulo_id, cantidad_a_acreditar) ya validados.
    a_acreditar: list[tuple[int, Decimal]] = []
    if not datos.renglones:
        # Total: todo lo que reste de cada renglón.
        for articulo_id in vendido:
            restante = _restante(articulo_id)
            if restante > 0:
                a_acreditar.append((articulo_id, restante))
    else:
        # Parcial: subconjunto validado renglón por renglón.
        for renglon in datos.renglones:
            articulo = catalogo.obtener_articulo(session, org_id, renglon.articulo_codigo)
            if articulo is None:
                raise NotaCreditoInvalida(
                    f"No existe el artículo {renglon.articulo_codigo!r} en tu organización."
                )
            if articulo.id not in vendido:
                raise NotaCreditoInvalida(
                    f"El artículo {articulo.codigo} no está en la venta {original.id}."
                )
            restante = _restante(articulo.id)
            if renglon.cantidad > restante:
                raise NotaCreditoInvalida(
                    f"No podés acreditar {renglon.cantidad} de {articulo.codigo}: "
                    f"restan {restante} (vendido {vendido[articulo.id].cantidad_vendida})."
                )
            a_acreditar.append((articulo.id, renglon.cantidad))

    if not a_acreditar:
        raise NotaCreditoInvalida(f"La venta {original.id} ya está totalmente acreditada.")

    # Congelar precio/IVA del original y calcular importes (mismo redondeo que la venta).
    resueltos: list[tuple[int, Decimal, Decimal, Decimal, Decimal]] = []
    for articulo_id, cantidad in a_acreditar:
        v = vendido[articulo_id]
        base = (cantidad * v.precio_unitario).quantize(_CENT, ROUND_HALF_UP)
        importe_iva = (base * v.alicuota_iva / Decimal(100)).quantize(_CENT, ROUND_HALF_UP)
        resueltos.append((articulo_id, cantidad, v.precio_unitario, base, importe_iva))

    neto = sum((base for _a, _c, _p, base, _iv in resueltos), Decimal("0"))
    iva = sum((importe_iva for _a, _c, _p, _b, importe_iva in resueltos), Decimal("0"))

    numero = asignar_numero(session, org_id, tipo="NC", pto_venta=original.pto_venta)

    nota = NotaCredito(
        org_id=org_id,
        ref_comprobante_id=original.id,
        cliente_id=original.cliente_id,
        deposito_id=original.deposito_id,
        tipo="NC",
        pto_venta=original.pto_venta,
        numero=numero,
        condicion=original.condicion,
        neto=neto,
        iva=iva,
        total=neto + iva,
        creado_por=usuario_id,
    )
    if fecha is not None:
        nota.fecha = fecha
    session.add(nota)
    session.flush()  # ⇐ acá pega el unique si el número ya existe: IntegrityError → 409

    for articulo_id, cantidad, precio_unitario, base, importe_iva in resueltos:
        session.add(
            NotaCreditoItem(
                org_id=org_id,
                nota_credito_id=nota.id,
                articulo_id=articulo_id,
                cantidad=cantidad,
                precio_unitario=precio_unitario,
                alicuota_iva=vendido[articulo_id].alicuota_iva,
                importe_iva=importe_iva,
                total_renglon=base + importe_iva,
            )
        )
        inventario.registrar_movimiento(
            session,
            org_id,
            articulo_id=articulo_id,
            deposito_id=original.deposito_id,
            cantidad=cantidad,  # positivo: vuelve al stock
            motivo="devolucion",
            ref_tipo="nota_credito",
            ref_id=nota.id,
            usuario_id=usuario_id,
        )

    # NC de una venta a crédito → un Haber que baja la deuda. La de contado no toca la cta cte
    # (el reintegro es plata de caja, fase futura).
    if original.condicion == "cta_cte":
        movimiento = CtaCteMovimiento(
            org_id=org_id,
            cliente_id=original.cliente_id,
            tipo="nota_credito",
            haber=nota.total,
            ref_tipo="nota_credito",
            ref_id=nota.id,
            creado_por=usuario_id,
        )
        if fecha is not None:
            movimiento.fecha = fecha
        session.add(movimiento)

    session.flush()
    return nota


def obtener_nota_credito(session: Session, org_id: UUID, nota_id: int) -> NotaCredito | None:
    return session.scalar(
        select(NotaCredito).where(NotaCredito.org_id == org_id, NotaCredito.id == nota_id)
    )


def items_de_nota_credito(session: Session, org_id: UUID, nota_id: int) -> list[NotaCreditoItem]:
    return list(
        session.scalars(
            select(NotaCreditoItem)
            .where(
                NotaCreditoItem.org_id == org_id,
                NotaCreditoItem.nota_credito_id == nota_id,
            )
            .order_by(NotaCreditoItem.id)
        )
    )


def listar_notas_credito(
    session: Session, org_id: UUID, *, limite: int = 50, offset: int = 0
) -> tuple[list[NotaCredito], int]:
    """Lista paginada + total, más reciente primero. Filtro por org_id explícito además del RLS."""
    total = (
        session.scalar(
            select(func.count()).select_from(NotaCredito).where(NotaCredito.org_id == org_id)
        )
        or 0
    )
    items = session.scalars(
        select(NotaCredito)
        .where(NotaCredito.org_id == org_id)
        .order_by(NotaCredito.fecha.desc(), NotaCredito.id.desc())
        .limit(limite)
        .offset(offset)
    )
    return list(items), total
