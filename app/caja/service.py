"""Caja: el libro del dinero.

No abre sesión ni commitea — recibe la del request y termina en flush(); el commit lo hace
`get_tenant` (app/core/rls.py). Mismo contrato que el resto de los services.

Este PR cubre la CARGA MANUAL. La derivación desde el recibo y la orden de pago llega en el
siguiente, y con ella sale `'cobranza'` de `MOVIMIENTOS_REVERSIBLES`.
"""

from datetime import date
from decimal import Decimal
from typing import Any
from uuid import UUID

from sqlalchemy import Row, func, select
from sqlalchemy.orm import Session

from app.caja.models import CajaMovimiento, CajaSaldo
from app.core.conceptos_caja import CONCEPTOS_DERIVADOS, CONCEPTOS_MANUALES, es_ingreso
from app.core.formas_pago import FORMAS_PAGO


class CajaInvalida(ValueError):
    """Error de negocio de caja. El router lo traduce a 422."""


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
