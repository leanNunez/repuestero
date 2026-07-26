"""Caja: el libro del dinero.

No abre sesión ni commitea — recibe la del request y termina en flush(); el commit lo hace
`get_tenant` (app/core/rls.py). Mismo contrato que el resto de los services.

Este PR cubre la CARGA MANUAL. La derivación desde el recibo y la orden de pago llega en el
siguiente, y con ella sale `'cobranza'` de `MOVIMIENTOS_REVERSIBLES`.
"""

from collections.abc import Sequence
from datetime import date
from decimal import Decimal
from typing import Any, NamedTuple
from uuid import UUID

from sqlalchemy import Row, func, select
from sqlalchemy.orm import Session

from app.caja.models import CajaMovimiento, CajaSaldo, Cheque
from app.core.conceptos_caja import CONCEPTOS_DERIVADOS, CONCEPTOS_MANUALES, es_ingreso
from app.core.formas_pago import FORMAS_PAGO

#: Estado inicial de un cheque que entra a la cartera.
EN_CARTERA = "en_cartera"

#: Estado terminal de un cheque cuyo documento se dio de baja.
ANULADO = "anulado"


class CajaInvalida(ValueError):
    """Error de negocio de caja. El router lo traduce a 422."""


class Asiento(NamedTuple):
    """Lo que un documento dejó escrito en caja: sus movimientos y los cheques que generó."""

    movimientos: list[CajaMovimiento]
    cheques: list[Cheque]


def registrar_movimiento(
    session: Session,
    org_id: UUID,
    *,
    concepto: str,
    forma: str,
    monto: Decimal,
    detalle: str | None = None,
    fecha: date | None = None,
    usuario_id: UUID | None = None,
) -> CajaMovimiento:
    """Carga a mano un movimiento de caja. Devuelve la fila escrita.

    El SIGNO no se pide: lo determina el concepto (`conceptos_caja.es_ingreso`). Pedirle al
    operador que elija "ingreso o egreso" además de "gasto" es pedirle que diga dos veces lo
    mismo, y la segunda vez es la que se contradice — la base rechazaría un 'gasto' cargado como
    ingreso, pero recién después de que alguien lo tipeó.

    **Solo acepta conceptos MANUALES.** Es la reja del invariante del módulo: si hay documento,
    caja no se toca a mano. Sin esto alguien podría cargar "cobranza $5.000" además del recibo que
    ya la generó, y la caja diría el doble de lo que hay en el cajón. Esos conceptos los escribe
    el sistema, con su `ref_tipo`/`ref_id` apuntando al documento.

    `fecha` es CUÁNDO se movió la plata, no cuándo se cargó. Sin límite de antigüedad acá a
    propósito: la ventana es política de la API (`app/core/fechas.py`), igual que en los dos
    ledgers de cuenta corriente.
    """
    if monto <= 0:
        raise CajaInvalida("El monto del movimiento debe ser mayor a cero.")

    if concepto in CONCEPTOS_DERIVADOS:
        raise CajaInvalida(
            f"El concepto {concepto!r} lo emite el sistema cuando se registra el documento que "
            "lo genera; no se carga a mano."
        )

    if concepto not in CONCEPTOS_MANUALES:
        raise CajaInvalida(f"No existe el concepto de caja {concepto!r}.")

    movimiento = CajaMovimiento(
        org_id=org_id,
        concepto=concepto,
        forma=forma,
        detalle=detalle,
        creado_por=usuario_id,
    )
    # El CHECK `concepto_coherente` de la 0011 impone lo mismo desde la base. Acá se decide, allá
    # se hace cumplir: si algún día alguien escribe una fila por otro camino, la base no la deja.
    if es_ingreso(concepto):
        movimiento.ingreso = monto
        movimiento.egreso = Decimal("0")
    else:
        movimiento.egreso = monto
        movimiento.ingreso = Decimal("0")

    if fecha is not None:
        movimiento.fecha = fecha

    session.add(movimiento)
    session.flush()
    return movimiento


def asentar_documento(
    session: Session,
    org_id: UUID,
    *,
    concepto: str,
    ref_tipo: str,
    ref_id: int,
    formas: Sequence[tuple[str, Decimal]],
    fecha: date | None = None,
    usuario_id: UUID | None = None,
) -> Asiento:
    """Escribe en caja lo que un documento movió. UN movimiento por forma de pago.

    Es el otro lado de `registrar_movimiento`: acá el concepto TIENE que ser derivado, porque
    estas filas las emite el sistema y llevan la referencia al documento que las causó. Las dos
    funciones son la misma reja mirada desde cada lado.

    Un renglón `'cheque'` genera además su fila en la CARTERA. Es lo que
    `app/core/formas_pago.py:12-15` dejó anotado desde que existe el recibo: "cada renglón de
    forma de pago se convierte en un cheque de la cartera. Esa es la razón de que el detalle sea
    1:N y no una columna: un recibo puede cancelarse con dos cheques distintos".

    El cheque nace con el importe y la referencia, y SIN banco ni número: un renglón de forma de
    pago no los trae. Completarlos es tarea de la pantalla de cartera.

    `formas` viaja como tuplas `(forma, monto)` y no como el `FormaPago` de ventas a propósito:
    caja no conoce los tipos de ventas ni de compras — si los importara, el módulo de más abajo
    dependería de los de más arriba y la dependencia quedaría al revés.
    """
    if concepto not in CONCEPTOS_DERIVADOS:
        raise CajaInvalida(
            f"El concepto {concepto!r} no lo emite un documento; se carga a mano con "
            "`registrar_movimiento`."
        )
    if not formas:
        raise CajaInvalida("Un documento sin formas de pago no mueve caja.")

    entra = es_ingreso(concepto)
    movimientos: list[CajaMovimiento] = []
    cheques: list[Cheque] = []

    for forma, monto in formas:
        if monto <= 0:
            raise CajaInvalida("El monto de cada forma de pago debe ser mayor a cero.")

        movimiento = CajaMovimiento(
            org_id=org_id,
            concepto=concepto,
            forma=forma,
            ingreso=monto if entra else Decimal("0"),
            egreso=Decimal("0") if entra else monto,
            ref_tipo=ref_tipo,
            ref_id=ref_id,
            creado_por=usuario_id,
        )
        if fecha is not None:
            movimiento.fecha = fecha
        session.add(movimiento)
        movimientos.append(movimiento)

        if forma == "cheque":
            cheque = Cheque(
                org_id=org_id,
                # Si entra plata, el cheque me lo dieron; si sale, lo firmé yo. No hace falta que
                # el caller lo diga: ya lo dijo eligiendo el concepto.
                origen="recibido" if entra else "emitido",
                importe=monto,
                estado=EN_CARTERA,
                ref_tipo=ref_tipo,
                ref_id=ref_id,
                creado_por=usuario_id,
            )
            session.add(cheque)
            cheques.append(cheque)

    session.flush()
    return Asiento(movimientos=movimientos, cheques=cheques)


def cheques_de_documento(
    session: Session, org_id: UUID, *, ref_tipo: str, ref_id: int
) -> list[Cheque]:
    """Los cheques que generó un documento, en el orden en que se cargaron."""
    return list(
        session.scalars(
            select(Cheque)
            .where(Cheque.org_id == org_id, Cheque.ref_tipo == ref_tipo, Cheque.ref_id == ref_id)
            .order_by(Cheque.id)
        )
    )


def revertir_documento(
    session: Session,
    org_id: UUID,
    *,
    concepto: str,
    ref_tipo: str,
    ref_id: int,
    usuario_id: UUID | None = None,
) -> Asiento:
    """Deshace en caja lo que un documento había movido, y saca sus cheques de la cartera.

    No edita nada: escribe el movimiento CONTRARIO por cada uno de los originales, que es como se
    corrige un libro append-only. El saldo vuelve a donde estaba porque la suma se cancela, no
    porque alguien haya borrado una fila.

    **Un cheque que ya se movió bloquea la anulación.** Si se depositó, se cobró o se entregó, el
    dinero ya siguió su camino fuera de este documento y deshacerlo desde acá dejaría la cartera
    diciendo una cosa y el banco otra. Ese caso se resuelve con el flujo del cheque (rechazo,
    devolución), no anulando el papel que lo trajo.
    """
    originales = list(
        session.scalars(
            select(CajaMovimiento).where(
                CajaMovimiento.org_id == org_id,
                CajaMovimiento.ref_tipo == ref_tipo,
                CajaMovimiento.ref_id == ref_id,
            )
        )
    )

    cheques = cheques_de_documento(session, org_id, ref_tipo=ref_tipo, ref_id=ref_id)
    movidos = [c for c in cheques if c.estado != EN_CARTERA]
    if movidos:
        estados = ", ".join(sorted({c.estado for c in movidos}))
        raise CajaInvalida(
            f"No se puede anular: el documento tiene cheques que ya se movieron ({estados}). "
            "Resolvelo desde la cartera."
        )

    contrarios: list[CajaMovimiento] = []
    for original in originales:
        contrario = CajaMovimiento(
            org_id=org_id,
            concepto=concepto,
            forma=original.forma,
            # El espejo: lo que entró vuelve a salir y al revés.
            ingreso=original.egreso,
            egreso=original.ingreso,
            ref_tipo=ref_tipo,
            ref_id=ref_id,
            creado_por=usuario_id,
        )
        session.add(contrario)
        contrarios.append(contrario)

    for cheque in cheques:
        cheque.estado = ANULADO

    session.flush()
    return Asiento(movimientos=contrarios, cheques=cheques)


def saldo_por_forma(session: Session, org_id: UUID) -> dict[str, Decimal]:
    """Cuánto hay, discriminado por forma. Leído de la VISTA `caja_saldo`.

    Devuelve TODAS las formas del catálogo, incluidas las que no tienen movimientos: la vista no
    trae fila para esas (igual que `cliente_saldo` con un cliente que nunca operó), y devolver un
    dict incompleto haría que cada caller tenga que acordarse del `.get(forma, 0)`. La ausencia de
    fila ES el cero, y ese detalle se resuelve una sola vez, acá.
    """
    saldos = {forma: Decimal("0") for forma in FORMAS_PAGO}
    filas = session.execute(
        select(CajaSaldo.forma, CajaSaldo.saldo).where(CajaSaldo.org_id == org_id)
    ).all()
    for forma, saldo in filas:
        saldos[forma] = saldo
    return saldos


def saldo_efectivo(session: Session, org_id: UUID) -> Decimal:
    """Lo que tiene que haber en el cajón. Es LA pregunta de caja, y por eso tiene función propia
    en vez de hacer que cada caller se acuerde de filtrar por `'efectivo'`."""
    return saldo_por_forma(session, org_id)["efectivo"]


def movimientos(
    session: Session,
    org_id: UUID,
    *,
    forma: str | None = None,
    limite: int = 50,
    offset: int = 0,
) -> tuple[list[Row[Any]], int]:
    """Extracto paginado, más reciente primero, con el saldo acumulado de cada renglón.

    El acumulado se calcula acá y NUNCA en el front, por la misma razón que en el extracto de
    cuenta corriente: el front recibe una ventana [offset, offset+limite) y el acumulado de su
    primera fila depende de todas las páginas anteriores. Calcularlo del lado del cliente exigiría
    traer el libro entero, que es lo que la paginación existe para evitar.

    **La window particiona por (org, FORMA)**, así que `saldo_acumulado` es "cuánto había de ESTA
    forma después de este movimiento". Es la lectura que sirve: mezclar el cajón con lo que entró
    por transferencia daría un número que no se corresponde con nada que se pueda contar.

    Por eso el filtro `forma` es seguro y un filtro por fecha NO lo sería: filtrar por forma saca
    particiones ENTERAS y deja intacta la que queda, mientras que un rango de fechas cortaría
    dentro de la partición y el acumulado arrancaría de cero en el rango, mal y en silencio. El
    día que haga falta filtrar por fecha, el rango va afuera de la subquery.
    """
    acumulado = (
        func.sum(CajaMovimiento.ingreso - CajaMovimiento.egreso)
        .over(
            partition_by=(CajaMovimiento.org_id, CajaMovimiento.forma),
            order_by=(CajaMovimiento.fecha, CajaMovimiento.id),
            # ROWS explícito. El frame por defecto es RANGE, y en RANGE todas las filas con la
            # misma `fecha` son peers y comparten el acumulado de cierre del día: dos movimientos
            # del mismo día —el caso normal— mostrarían el mismo saldo.
            rows=(None, 0),
        )
        .label("saldo_acumulado")
    )

    filtros = [CajaMovimiento.org_id == org_id]
    if forma is not None:
        filtros.append(CajaMovimiento.forma == forma)

    total = session.scalar(select(func.count()).select_from(CajaMovimiento).where(*filtros)) or 0

    # La window va en una subquery y el orden de lectura afuera: Postgres evalúa las window
    # functions después del WHERE y antes del LIMIT, así que sin este nivel el LIMIT recortaría
    # antes de acumular. Mismo patrón que `ventas.movimientos_cliente`.
    libro = (
        select(
            CajaMovimiento.id,
            CajaMovimiento.fecha,
            CajaMovimiento.concepto,
            CajaMovimiento.forma,
            CajaMovimiento.ingreso,
            CajaMovimiento.egreso,
            CajaMovimiento.detalle,
            CajaMovimiento.ref_tipo,
            CajaMovimiento.ref_id,
            # Cuándo se CARGÓ, además de cuándo pasó. Con fechas retroactivas las dos verdades
            # dejan de coincidir, y sin esto el retroactivo sería una forma prolija de reescribir
            # el pasado.
            CajaMovimiento.creado_en,
            acumulado,
        )
        .where(*filtros)
        .subquery()
    )

    filas = session.execute(
        select(libro).order_by(libro.c.fecha.desc(), libro.c.id.desc()).limit(limite).offset(offset)
    ).all()

    return list(filas), total
