"""Orquestación de ventas. NO escribe SQL crudo: compone los services de cada módulo.

El dueño de `articulos` es `catalogo`, el de `clientes` es `clientes`, y el ÚNICO camino al
stock es `inventario.registrar_movimiento`. Este módulo los usa; nunca toca sus tablas directo
(mismo criterio que `app/ingesta_visual/service.py`).

Una venta es UNA transacción todo-o-nada: o entran la cabecera, todos los renglones y todos los
movimientos de stock, o no entra nada. No abre sesión ni commitea — recibe la del request y
termina en flush(); el commit lo hace `get_tenant` (app/core/rls.py).
"""

from collections.abc import Sequence
from datetime import date
from decimal import ROUND_HALF_UP, Decimal
from typing import Any, NamedTuple
from uuid import UUID

from sqlalchemy import Row, and_, func, join, or_, select
from sqlalchemy.orm import Session, aliased

from app.caja import service as caja
from app.catalogo import service as catalogo
from app.clientes import service as clientes
from app.clientes.models import Cliente
from app.core.formas_pago import FORMAS_PAGO
from app.core.numeracion import asignar_numero
from app.inventario import service as inventario
from app.ventas.models import (
    ClienteSaldo,
    Comprobante,
    ComprobanteItem,
    CtaCteMovimiento,
    NotaCredito,
    NotaCreditoItem,
    Recibo,
    ReciboFormaPago,
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

#: `ref_tipo` de un ajuste que revierte a otro movimiento; su `ref_id` apunta al original.
REF_REVERSA = "ajuste_de"

#: `ref_tipo` del movimiento que genera una cobranza; su `ref_id` apunta al recibo emitido.
REF_RECIBO = "recibo"

#: Con qué `tipo` se numeran los recibos (`Numerador`). Espacio propio: no comparten contador con
#: las facturas ni con las notas de crédito.
TIPO_RECIBO = "REC"

#: Con qué `concepto` viaja a caja el dinero de un recibo, y con cuál vuelve al anularlo.
CONCEPTO_COBRANZA = "cobranza"
CONCEPTO_ANULA_COBRANZA = "anulacion_cobranza"

#: Qué se puede revertir con un storno DESDE EL EXTRACTO. Deliberadamente NO están 'venta' ni
#: 'nota_credito': esos movimientos ESPEJAN un comprobante, y cancelar su efecto desde el ledger
#: dejaría el comprobante vivo con su cuenta corriente en cero — el ledger dejaría de espejar los
#: comprobantes, en silencio. Es el pecado del legacy que este diseño existe para no repetir. Una
#: venta se revierte con una NOTA DE CRÉDITO, que ya existe.
#:
#: 'cobranza' SALIÓ de esta lista al llegar `app/caja/`, y esta nota registra el porqué porque la
#: pregunta va a volver. Mientras el recibo no tenía efectos fuera del ledger, revertir el Haber
#: cancelaba el 100% de su efecto y no quedaba nada huérfano. Desde que un recibo mueve un ingreso
#: de caja y mete un cheque en la cartera, revertir solo el ledger deja esas dos cosas vivas —
#: exactamente el problema que 'venta' tiene—. La anulación correcta es `anular_recibo`: reversa
#: del ledger + reversa de caja + baja del cheque, en una transacción.
#:
#: Queda 'ajuste', que sigue siendo reversible porque un ajuste NO tiene efectos fuera del ledger:
#: es una fila de corrección y nada más. Es la única que se revierte desde el extracto.
MOVIMIENTOS_REVERSIBLES = frozenset({"ajuste"})


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


class FormaPago(NamedTuple):
    """Con qué se cobró una parte del recibo. `forma` tiene que estar en `FORMAS_PAGO`."""

    forma: str
    monto: Decimal


class Cobranza(NamedTuple):
    """Lo que deja una cobranza: el documento y su asiento.

    Se devuelven los dos porque el router necesita el número de recibo para el acuse Y el
    movimiento para recalcular el saldo.
    """

    recibo: Recibo
    movimiento: CtaCteMovimiento


def _validar_formas(formas: Sequence[FormaPago], total: Decimal) -> None:
    """Las formas tienen que existir, ser positivas y sumar EXACTO el total.

    Duplica lo que ya garantiza la base (CHECK + constraint trigger de la 0010), y es a propósito:
    acá el error sale como `VentaInvalida` → 422 con un mensaje que el operador entiende. El
    trigger diferido dispara recién en el COMMIT, o sea DESPUÉS de que el endpoint respondió, y
    saldría como 500. La base es la garantía; esto es la cortesía.
    """
    if not formas:
        raise VentaInvalida("Decí con qué se cobró: falta el detalle de formas de pago.")

    for f in formas:
        if f.forma not in FORMAS_PAGO:
            opciones = ", ".join(sorted(FORMAS_PAGO))
            raise VentaInvalida(f"Forma de pago desconocida: {f.forma!r}. Puede ser: {opciones}.")
        if f.monto <= 0:
            raise VentaInvalida(f"El monto de {f.forma!r} debe ser mayor a cero.")

    suma = sum((f.monto for f in formas), Decimal("0")).quantize(_CENT, ROUND_HALF_UP)
    if suma != total.quantize(_CENT, ROUND_HALF_UP):
        raise VentaInvalida(
            f"Las formas de pago suman {suma} y la cobranza es de {total}. Tienen que coincidir."
        )


def registrar_cobranza(
    session: Session,
    org_id: UUID,
    *,
    cliente_codigo: str,
    monto: Decimal,
    formas_pago: Sequence[FormaPago],
    fecha: date | None = None,
    pto_venta: int = 1,
    usuario_id: UUID | None = None,
) -> Cobranza:
    """Emite un RECIBO y lo imputa como un Haber en la cuenta corriente. Baja el saldo.

    El recibo es el documento del cobro, y es lo que le faltaba a este ledger: antes de existir,
    la cobranza escribía un Haber suelto con `ref_tipo`/`ref_id` en NULL mientras la venta y la
    nota de crédito sí referenciaban el suyo. Ahora el movimiento apunta al recibo con
    `ref_tipo='recibo'`.

    `formas_pago` es OBLIGATORIA acá, aunque el borde HTTP la deje omitir y asuma efectivo. La
    asimetría es deliberada, la misma de `validar_fecha_movimiento`: "si no me decís con qué te
    pagaron, asumo efectivo" es política de mostrador, no un invariante del dominio. El importador
    de Paradox entra por este camino y SÍ tiene el dato real (`CLIENTESCTACTEFORMAPAGO`), así que
    nunca debe recibir un "efectivo" inventado en silencio.

    `fecha` es CUÁNDO ENTRÓ la plata, no cuándo se cargó: la del viernes tipeada el lunes va con la
    del viernes, y el recibo se fecha igual que su movimiento. Si no viene, queda el `current_date`
    de la tabla. `creado_en` guarda el momento real del alta, así que las dos verdades conviven y
    el retroactivo es auditable.

    Sin límite de antigüedad acá a propósito: la ventana es política de la API
    (`app/core/fechas.py`) y el importador entra con años de historia.

    No abre sesión ni commitea (termina en flush), igual que el resto. El saldo se recalcula
    solo desde la vista: no hay columna que actualizar.
    """
    if monto <= 0:
        raise VentaInvalida("El monto de la cobranza debe ser mayor a cero.")

    _validar_formas(formas_pago, monto)

    cliente = clientes.obtener_cliente(session, org_id, cliente_codigo)
    if cliente is None:
        raise VentaInvalida(f"No existe el cliente {cliente_codigo!r} en tu organización.")

    numero = asignar_numero(session, org_id, tipo=TIPO_RECIBO, pto_venta=pto_venta)
    recibo = Recibo(
        org_id=org_id,
        cliente_id=cliente.id,
        tipo=TIPO_RECIBO,
        pto_venta=pto_venta,
        numero=numero,
        total=monto,
        creado_por=usuario_id,
    )
    if fecha is not None:
        recibo.fecha = fecha
    session.add(recibo)
    session.flush()  # ⇐ acá pega el unique si el número ya existe: IntegrityError → 409

    for f in formas_pago:
        session.add(
            ReciboFormaPago(org_id=org_id, recibo_id=recibo.id, forma=f.forma, monto=f.monto)
        )

    movimiento = CtaCteMovimiento(
        org_id=org_id,
        cliente_id=cliente.id,
        tipo="cobranza",
        haber=monto,
        ref_tipo=REF_RECIBO,
        ref_id=recibo.id,
        creado_por=usuario_id,
    )
    if fecha is not None:
        movimiento.fecha = fecha
    session.add(movimiento)

    # La plata ENTRA a la caja, en la MISMA transacción que el recibo y el asiento de cuenta
    # corriente. Antes de esto el saldo del cliente bajaba y el dinero no aparecía en ningún lado.
    # Un renglón de forma 'cheque' además entra a la cartera.
    caja.asentar_documento(
        session,
        org_id,
        concepto=CONCEPTO_COBRANZA,
        ref_tipo=REF_RECIBO,
        ref_id=recibo.id,
        formas=[(f.forma, f.monto) for f in formas_pago],
        fecha=fecha,
        usuario_id=usuario_id,
    )

    session.flush()
    return Cobranza(recibo=recibo, movimiento=movimiento)


def anular_recibo(
    session: Session,
    org_id: UUID,
    recibo_id: int,
    *,
    motivo: str,
    usuario_id: UUID | None = None,
) -> CtaCteMovimiento:
    """Anula un recibo: revierte el ledger, revierte la caja y saca sus cheques de la cartera.

    Es la operación que REEMPLAZA a "revertir la cobranza desde el extracto", y existe porque un
    recibo dejó de tener un solo efecto. Mientras el recibo no movía nada fuera del ledger,
    revertir el Haber cancelaba el 100% de su efecto; desde que mueve caja y cartera, revertir
    solo el ledger deja esas dos cosas vivas — el pecado del legacy que este diseño existe para
    no repetir. Por eso `'cobranza'` salió de `MOVIMIENTOS_REVERSIBLES`.

    Las TRES reversas van en la misma transacción: o se deshace todo o no se deshace nada.

    El recibo NO se toca (es append-only, y sigue sin tener columna `anulado`): el estado queda
    DERIVADO de que existe una reversa del movimiento que lo referencia, igual que antes. Una
    fila menos que pueda desincronizarse.
    """
    motivo = motivo.strip()
    if not motivo:
        raise VentaInvalida("La anulación necesita un motivo: sin él nadie puede explicarla.")

    recibo = obtener_recibo(session, org_id, recibo_id)
    if recibo is None:
        raise VentaInvalida("No existe ese recibo en tu organización.")

    movimiento = session.scalar(
        select(CtaCteMovimiento).where(
            CtaCteMovimiento.org_id == org_id,
            CtaCteMovimiento.ref_tipo == REF_RECIBO,
            CtaCteMovimiento.ref_id == recibo.id,
        )
    )
    if movimiento is None:
        raise VentaInvalida("Ese recibo no tiene un movimiento de cuenta corriente que revertir.")

    # Chequeo previo solo para dar un error legible: la garantía REAL es el índice único parcial
    # de la 0009, porque entre este SELECT y el INSERT entra otra transacción.
    if session.scalar(
        select(CtaCteMovimiento.id).where(
            CtaCteMovimiento.org_id == org_id,
            CtaCteMovimiento.ref_tipo == REF_REVERSA,
            CtaCteMovimiento.ref_id == movimiento.id,
        )
    ):
        raise VentaInvalida("Ese recibo ya fue anulado.")

    # La caja PRIMERO: si el documento tiene cheques que ya se movieron, esto levanta y no queda
    # un ledger revertido con la cartera intacta.
    try:
        caja.revertir_documento(
            session,
            org_id,
            concepto=CONCEPTO_ANULA_COBRANZA,
            ref_tipo=REF_RECIBO,
            ref_id=recibo.id,
            usuario_id=usuario_id,
        )
    except caja.CajaInvalida as exc:
        raise VentaInvalida(str(exc)) from None

    reversa = CtaCteMovimiento(
        org_id=org_id,
        cliente_id=movimiento.cliente_id,
        tipo="ajuste",
        # El espejo exacto: el Haber de la cobranza vuelve como Debe.
        debe=movimiento.haber,
        haber=movimiento.debe,
        ref_tipo=REF_REVERSA,
        ref_id=movimiento.id,
        motivo=motivo,
        creado_por=usuario_id,
    )
    session.add(reversa)
    session.flush()
    return reversa


def obtener_recibo(session: Session, org_id: UUID, recibo_id: int) -> Recibo | None:
    return session.scalar(select(Recibo).where(Recibo.org_id == org_id, Recibo.id == recibo_id))


def formas_de_recibo(session: Session, org_id: UUID, recibo_id: int) -> list[ReciboFormaPago]:
    """El detalle de un recibo, en el orden en que se cargó."""
    return list(
        session.scalars(
            select(ReciboFormaPago)
            .where(ReciboFormaPago.org_id == org_id, ReciboFormaPago.recibo_id == recibo_id)
            .order_by(ReciboFormaPago.id)
        )
    )


def registrar_ajuste(
    session: Session,
    org_id: UUID,
    *,
    cliente_id: int,
    motivo: str,
    debe: Decimal | None = None,
    haber: Decimal | None = None,
    revierte_movimiento_id: int | None = None,
    fecha: date | None = None,
    usuario_id: UUID | None = None,
) -> CtaCteMovimiento:
    """Corrige la cuenta corriente con una fila NUEVA. El pasado no se toca jamás.

    Es el mecanismo que el trigger de la 0006 viene reclamando desde que existe. UN solo
    mecanismo con dos usos, porque el segundo es el primero sin la ayuda del sistema:

    - **Reversa** (`revierte_movimiento_id`): el service LEE el movimiento original y escribe su
      espejo exacto (un haber de 5000 se revierte con un debe de 5000). El monto NO viaja en el
      pedido: así no se puede errar tipeando, que es justo el error que se está corrigiendo.
    - **Manual** (`debe` o `haber`): saldo inicial de una migración, condonación, redondeo. Acá el
      importe sí lo pone la persona, y por eso el motivo pesa más todavía.

    `motivo` es obligatorio en los dos casos — un ajuste sin motivo es una fila que en seis meses
    nadie puede explicar. El CHECK de la 0009 lo respalda en la base.

    `fecha` permite ubicar el ajuste cuando corresponde (un saldo inicial de migración no es de
    hoy). Si no viene, queda el `current_date` de la tabla.

    No abre sesión ni commitea (termina en flush), igual que el resto. El saldo sale solo de la
    vista: no hay columna que actualizar.
    """
    motivo = motivo.strip()
    if not motivo:
        raise VentaInvalida("El ajuste necesita un motivo: sin él la corrección no se puede leer.")

    cliente = clientes.obtener_cliente_por_id(session, org_id, cliente_id)
    if cliente is None:
        raise VentaInvalida("No existe ese cliente en tu organización.")

    ref_tipo: str | None = None
    ref_id: int | None = None

    if revierte_movimiento_id is not None:
        if debe is not None or haber is not None:
            raise VentaInvalida(
                "Una reversa no lleva importe: lo calcula el sistema desde el movimiento original."
            )

        # El filtro por `cliente_id` no es redundante con el de org: sin él se podría revertir el
        # movimiento de OTRO cliente de la misma organización pasando su id a mano.
        original = session.scalar(
            select(CtaCteMovimiento).where(
                CtaCteMovimiento.org_id == org_id,
                CtaCteMovimiento.id == revierte_movimiento_id,
                CtaCteMovimiento.cliente_id == cliente_id,
            )
        )
        if original is None:
            raise VentaInvalida("No existe ese movimiento en la cuenta de este cliente.")

        if original.tipo not in MOVIMIENTOS_REVERSIBLES:
            raise VentaInvalida(
                f"Un movimiento de tipo {original.tipo!r} no se revierte desde la cuenta "
                "corriente porque refleja un comprobante. Emití una nota de crédito."
            )

        # Chequeo previo solo para dar un error legible: la garantía REAL es el índice único
        # parcial de la 0009, porque entre este SELECT y el INSERT entra otra transacción.
        if session.scalar(
            select(CtaCteMovimiento.id).where(
                CtaCteMovimiento.org_id == org_id,
                CtaCteMovimiento.ref_tipo == REF_REVERSA,
                CtaCteMovimiento.ref_id == original.id,
            )
        ):
            raise VentaInvalida("Ese movimiento ya fue revertido con un ajuste.")

        # El espejo: lo que era Haber vuelve como Debe y al revés. El saldo queda como antes.
        debe, haber = original.haber, original.debe
        ref_tipo, ref_id = REF_REVERSA, original.id
    else:
        importes = [m for m in (debe, haber) if m is not None]
        if not importes:
            raise VentaInvalida("Un ajuste manual lleva un importe en Debe o en Haber.")
        if len(importes) == 2:
            raise VentaInvalida("Un ajuste va en Debe o en Haber, no en los dos a la vez.")
        if importes[0] <= 0:
            raise VentaInvalida("El importe del ajuste debe ser mayor a cero.")

    movimiento = CtaCteMovimiento(
        org_id=org_id,
        cliente_id=cliente_id,
        tipo="ajuste",
        debe=debe if debe is not None else Decimal("0"),
        haber=haber if haber is not None else Decimal("0"),
        ref_tipo=ref_tipo,
        ref_id=ref_id,
        motivo=motivo,
        creado_por=usuario_id,
    )
    if fecha is not None:
        movimiento.fecha = fecha
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

    Cada fila trae además su `motivo`, un `anulado` y un `reversible`. `anulado` es lo que hace
    legible al storno: sin él el extracto muestra un haber de 5000 y un debe de 5000 y el operador
    tiene que adivinar que se cancelan entre sí. `reversible` responde "¿puedo apretar Revertir?"
    para que la regla de qué se puede revertir viva en UN solo lugar, y no también en el front.
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

    # ¿Alguien ya revirtió esta fila? EXISTS correlacionado sobre el MISMO ledger, así que hace
    # falta un alias para distinguir la reversa del movimiento revertido. Lo resuelve el índice
    # parcial `uq_cta_cte_movimientos_reversa` de la 0009.
    reversa = aliased(CtaCteMovimiento)
    ya_revertido = (
        select(reversa.id)
        .where(
            reversa.org_id == CtaCteMovimiento.org_id,
            reversa.ref_tipo == REF_REVERSA,
            reversa.ref_id == CtaCteMovimiento.id,
        )
        .exists()
    )

    anulado = ya_revertido.label("anulado")

    # La respuesta a "¿puedo apretar Revertir en esta fila?", resuelta ACÁ y no en el front. Junta
    # las dos condiciones a propósito: si viajara solo el tipo, el front tendría que combinarlo con
    # `anulado` y volveríamos a tener regla de negocio del lado del cliente.
    # `sorted()` sobre el frozenset para que el SQL salga igual en cada corrida.
    reversible = and_(
        CtaCteMovimiento.tipo.in_(sorted(MOVIMIENTOS_REVERSIBLES)),
        ~ya_revertido,
    ).label("reversible")

    filtros = (CtaCteMovimiento.org_id == org_id, CtaCteMovimiento.cliente_id == cliente_id)

    total = session.scalar(select(func.count()).select_from(CtaCteMovimiento).where(*filtros)) or 0

    # La window va en una subquery y el orden de lectura afuera. Hoy daría lo mismo en un solo
    # nivel (Postgres evalúa las window functions después del WHERE y antes del LIMIT), pero el
    # día que se filtre por rango de fechas el WHERE recortaría filas ANTES de acumular y el
    # saldo arrancaría de cero en el rango, mal y en silencio. El EXISTS va acá adentro por lo
    # mismo: afuera se evaluaría sobre la ventana ya recortada.
    ledger = (
        select(
            CtaCteMovimiento.id,
            CtaCteMovimiento.fecha,
            CtaCteMovimiento.tipo,
            CtaCteMovimiento.debe,
            CtaCteMovimiento.haber,
            CtaCteMovimiento.ref_tipo,
            CtaCteMovimiento.ref_id,
            CtaCteMovimiento.motivo,
            # Cuándo se CARGÓ, además de cuándo pasó. Con fechas retroactivas las dos verdades
            # dejan de coincidir, y sin esto el retroactivo sería una forma prolija de reescribir
            # el pasado: nadie podría ver que esa fila entró tres días después.
            CtaCteMovimiento.creado_en,
            anulado,
            reversible,
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
