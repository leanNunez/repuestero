"""Caja: el libro del dinero.

No abre sesión ni commitea — recibe la del request y termina en flush(); el commit lo hace
`get_tenant` (app/core/rls.py). Mismo contrato que el resto de los services.

Tres caminos escriben acá, y la diferencia importa:

- **Carga manual** (`registrar_movimiento`): un gasto, un retiro. Sin documento detrás, así que
  `ref_tipo`/`ref_id` quedan en NULL y solo acepta conceptos de `CONCEPTOS_MANUALES`.
- **Derivación** (`asentar_documento` / `revertir_documento`): lo emite un recibo o una orden de
  pago, en su misma transacción.
- **La cartera** (`depositar`, `cobrar`, `rechazar`, `entregar`): el ciclo de vida del papel, que
  escribe en caja cada vez que mueve plata.

El invariante que los separa: **si hay documento, caja no se toca a mano**.
"""

from collections.abc import Iterable, Sequence
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

#: En el banco, esperando que acredite. Todavía vale lo mismo: depositar NO mueve plata.
DEPOSITADO = "depositado"

#: Terminales. Un cheque que llegó acá no vuelve.
COBRADO = "cobrado"
RECHAZADO = "rechazado"
ENTREGADO = "entregado"

#: Estado terminal de un cheque cuyo documento se dio de baja.
ANULADO = "anulado"

#: La máquina de estados del papel, explícita y en un solo lugar.
#:
#: Un dict y no una cadena de `if` porque las transiciones válidas SON el dominio: escritas así se
#: leen de un vistazo, se testean recorriéndolas, y agregar un estado es tocar una línea en vez de
#: auditar todas las ramas de una función.
#:
#: Los cuatro terminales apuntan a un conjunto vacío. `anulado` entre ellos es lo que impide
#: resucitar un cheque cuyo documento se dio de baja: `revertir_documento` lo deja ahí y no hay
#: arista de salida.
TRANSICIONES: dict[str, frozenset[str]] = {
    EN_CARTERA: frozenset({DEPOSITADO, COBRADO, RECHAZADO, ENTREGADO}),
    # Un cheque en el banco solo puede acreditar o rebotar. No se "des-deposita", y endosarlo es
    # imposible: el papel ya no lo tenés en la mano.
    DEPOSITADO: frozenset({COBRADO, RECHAZADO}),
    COBRADO: frozenset(),
    RECHAZADO: frozenset(),
    ENTREGADO: frozenset(),
    ANULADO: frozenset(),
}

#: Un cheque que YO recibí: su ciclo de vida mueve mi caja.
RECIBIDO = "recibido"


class CajaInvalida(ValueError):
    """Error de negocio de caja. El router lo traduce a 422."""


class ChequeNoEncontrado(LookupError):
    """No existe ese cheque en esta organización. El router lo traduce a 404.

    Excepción aparte de `CajaInvalida` a propósito: "no existe" y "no se puede" son respuestas
    distintas, y confundirlas fue exactamente el bug de `GET /ventas/clientes/{id}/saldo` (PR #47),
    que devolvía 200 con saldo 0 para un cliente inexistente.
    """


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


# =================================================================== la cartera: ciclo del papel


def _buscar_cheque(session: Session, org_id: UUID, cheque_id: int) -> Cheque:
    """El cheque de ESTA org, o `ChequeNoEncontrado`.

    El filtro por `org_id` es redundante con el RLS y va igual: si algún día alguien llama a este
    service con una sesión sin el tenant seteado, la consulta sigue sin cruzar organizaciones.
    """
    cheque = session.scalars(
        select(Cheque).where(Cheque.org_id == org_id, Cheque.id == cheque_id)
    ).one_or_none()
    if cheque is None:
        raise ChequeNoEncontrado(f"No existe el cheque {cheque_id}.")
    return cheque


def _movimiento_de_cheque(
    org_id: UUID,
    cheque: Cheque,
    *,
    concepto: str,
    forma: str,
    fecha: date | None,
    usuario_id: UUID | None,
) -> CajaMovimiento:
    """Una fila de caja causada por la transición de un cheque.

    El signo lo decide el concepto, igual que en `registrar_movimiento`: acá no se pasa "ingreso o
    egreso" porque sería decir dos veces lo mismo y la segunda es la que se contradice.

    `ref_tipo='cheque'` (el valor ya estaba previsto en el comentario de `ref_tipo` de la 0011)
    deja el rastro de qué papel movió esta plata, que es lo que hace auditable el extracto.
    """
    entra = es_ingreso(concepto)
    movimiento = CajaMovimiento(
        org_id=org_id,
        concepto=concepto,
        forma=forma,
        ingreso=cheque.importe if entra else Decimal("0"),
        egreso=Decimal("0") if entra else cheque.importe,
        ref_tipo="cheque",
        ref_id=cheque.id,
        creado_por=usuario_id,
    )
    if fecha is not None:
        movimiento.fecha = fecha
    return movimiento


def _transicionar(
    session: Session,
    org_id: UUID,
    cheque_id: int,
    *,
    destino: str,
    fecha: date | None = None,
    usuario_id: UUID | None = None,
) -> Asiento:
    """Mueve un cheque de estado y escribe en caja lo que ese movimiento haya movido de plata.

    Es el único lugar que cambia `Cheque.estado`, junto con `revertir_documento`. Las cuatro
    funciones públicas de abajo son envoltorios finos sobre esto: la validación del grafo y los
    efectos en caja se escriben una sola vez.

    ## Por qué un cheque EMITIDO no toca la caja acá

    Cuando se registró la orden de pago, `asentar_documento` ya escribió
    `(forma='cheque', concepto='pago_proveedor', egreso=monto)`: **la plata ya salió**. Si al
    entregarle el papel al proveedor volviéramos a escribir un egreso, el mismo pago saldría dos
    veces de la caja.

    Así que para un emitido esto es solo el estado del papel — útil para saber si el proveedor ya
    lo depositó, sin efecto contable. El rebote de un cheque propio (que revive la deuda y devuelve
    la plata) se resuelve anulando la orden de pago con `compras.anular_orden_pago`, que deshace el
    asiento entero; no se parchea desde la cartera.
    """
    cheque = _buscar_cheque(session, org_id, cheque_id)

    if destino not in TRANSICIONES[cheque.estado]:
        posibles = ", ".join(sorted(TRANSICIONES[cheque.estado])) or "ninguno: es un estado final"
        raise CajaInvalida(
            f"Un cheque {cheque.estado!r} no puede pasar a {destino!r}. Posibles: {posibles}."
        )

    movimientos: list[CajaMovimiento] = []
    if cheque.origen == RECIBIDO:
        for concepto, forma in _efectos_en_caja(cheque.estado, destino):
            movimiento = _movimiento_de_cheque(
                org_id, cheque, concepto=concepto, forma=forma, fecha=fecha, usuario_id=usuario_id
            )
            session.add(movimiento)
            movimientos.append(movimiento)

    cheque.estado = destino
    session.flush()
    return Asiento(movimientos=movimientos, cheques=[cheque])


def _efectos_en_caja(origen_estado: str, destino: str) -> list[tuple[str, str]]:
    """Qué asientos escribe una transición, como `(concepto, forma)`.

    **Cobrar escribe DOS**, y esa es la lección que costó una migración: el papel sale de la
    cartera Y la plata entra por otra forma. Escribir solo la segunda pata dejaría la caja diciendo
    que tiene el cheque y el dinero — el doble de lo que hay. Ver `app/core/conceptos_caja.py`.

    En qué forma entra la plata depende del CAMINO, no del destino:

    - Cobrado desde `en_cartera` = lo cobré por ventanilla, entró al **cajón** (`efectivo`).
    - Cobrado desde `depositado` = lo acreditó el **banco** (`transferencia`, la única forma del
      vocabulario que representa dinero bancario).

    Sin esa distinción, `saldo_efectivo` diría que hay plata en el cajón que en realidad está en el
    banco, y dejaría de ser arqueable contra lo que se cuenta a mano — que es todo lo que promete.
    """
    if destino == DEPOSITADO:
        # El cheque cambió de lugar físico, no de valor: sigue siendo un cheque y sigue valiendo lo
        # mismo. No hay plata que mover.
        return []
    if destino == COBRADO:
        forma_destino = "efectivo" if origen_estado == EN_CARTERA else "transferencia"
        return [("cheque_cobrado_cartera", "cheque"), ("cheque_cobrado", forma_destino)]
    if destino == RECHAZADO:
        # El banco lo devolvió: el valor nunca existió. Sale de la cartera y no entra nada — la
        # deuda del cliente revive por el lado de la cuenta corriente, no acá.
        return [("cheque_rechazado", "cheque")]
    if destino == ENTREGADO:
        # Endoso: el papel se lo di a un proveedor. Sale de mi cartera y no entra nada a mi caja.
        return [("pago_proveedor", "cheque")]
    return []


def depositar(
    session: Session,
    org_id: UUID,
    cheque_id: int,
    *,
    fecha: date | None = None,  # noqa: ARG001 — ver el docstring
    usuario_id: UUID | None = None,
) -> Asiento:
    """Lo llevé al banco. No mueve plata: el cheque vale lo mismo antes y después.

    Acepta `fecha` y NO la usa, para que las cuatro transiciones tengan la misma firma y el router
    pueda tratarlas igual. No se guarda en ningún lado porque no hay dónde: `fecha` en este módulo
    es "cuándo se movió la plata", y acá no se movió ninguna. El día que haga falta saber cuándo se
    depositó, es una columna `fecha_deposito` en `cheques`, no este parámetro.
    """
    return _transicionar(session, org_id, cheque_id, destino=DEPOSITADO, usuario_id=usuario_id)


def cobrar(
    session: Session,
    org_id: UUID,
    cheque_id: int,
    *,
    fecha: date | None = None,
    usuario_id: UUID | None = None,
) -> Asiento:
    """Se hizo efectivo. Escribe las DOS patas: sale de la cartera, entra por efectivo (si fue por
    ventanilla) o por transferencia (si lo acreditó el banco). Ver `_efectos_en_caja`."""
    return _transicionar(
        session, org_id, cheque_id, destino=COBRADO, fecha=fecha, usuario_id=usuario_id
    )


def rechazar(
    session: Session,
    org_id: UUID,
    cheque_id: int,
    *,
    fecha: date | None = None,
    usuario_id: UUID | None = None,
) -> Asiento:
    """Volvió rechazado. Sale de la cartera sin acreditar nada."""
    return _transicionar(
        session, org_id, cheque_id, destino=RECHAZADO, fecha=fecha, usuario_id=usuario_id
    )


def entregar(
    session: Session,
    org_id: UUID,
    cheque_id: int,
    *,
    fecha: date | None = None,
    usuario_id: UUID | None = None,
) -> Asiento:
    """Endosado a un proveedor. Sale de la cartera como `pago_proveedor`."""
    return _transicionar(
        session, org_id, cheque_id, destino=ENTREGADO, fecha=fecha, usuario_id=usuario_id
    )


def conciliar(session: Session, org_id: UUID, cheque_id: int, *, fecha: date) -> Cheque:
    """Marca el cheque como conciliado contra el resumen bancario.

    Es ortogonal al estado: se concilia un cheque cobrado o uno rechazado, y el estado no cambia
    por conciliarlo. Por eso no pasa por la máquina de estados.

    La fecha es OBLIGATORIA —el CHECK `ck_cheques_conciliado_con_fecha` de la 0011 la exige— porque
    una conciliación sin fecha no se puede auditar, que es todo el punto de conciliar. El blueprint
    (§5.G) cuenta con esto: "cheques sin conciliar" es una de las anomalías que auditoría detecta.
    """
    cheque = _buscar_cheque(session, org_id, cheque_id)
    if cheque.conciliado:
        raise CajaInvalida(f"El cheque {cheque_id} ya estaba conciliado.")

    cheque.conciliado = True
    cheque.fecha_conciliacion = fecha
    session.flush()
    return cheque


def cartera(
    session: Session,
    org_id: UUID,
    *,
    estado: str | None = None,
    limite: int = 50,
    offset: int = 0,
) -> tuple[list[Cheque], int]:
    """Los cheques de la org, paginados. Sin `estado` trae todos.

    Sin window function ni saldo acumulado, a diferencia de `movimientos`: un cheque no acumula, es
    un papel con un importe. El total de la cartera se responde con `valor_en_cartera`.

    El orden es por `fecha_cobro` y después por id. Es la pregunta real del mostrador —"qué puedo
    depositar esta semana"—, y `ix_cheques_org_estado` (org, estado, fecha_cobro) ya cubre este
    acceso. Los que no tienen `fecha_cobro` cargada quedan al final (`nulls_last`) en vez de
    encabezar la lista, que es donde menos sirven.
    """
    filtros = [Cheque.org_id == org_id]
    if estado is not None:
        filtros.append(Cheque.estado == estado)

    total = session.scalar(select(func.count()).select_from(Cheque).where(*filtros)) or 0
    cheques = session.scalars(
        select(Cheque)
        .where(*filtros)
        .order_by(Cheque.fecha_cobro.asc().nulls_last(), Cheque.id)
        .limit(limite)
        .offset(offset)
    ).all()
    return list(cheques), total


def valor_en_cartera(session: Session, org_id: UUID) -> Decimal:
    """Cuánto valen los cheques que todavía tengo en la mano.

    Se lee de `cheques` y no de `caja_saldo['cheque']` a propósito, aunque los dos números tengan
    que coincidir: este es el inventario del papel y aquel es el libro del dinero. Que coincidan es
    justamente lo que un arqueo verifica — leerlos del mismo lugar haría que el control no controle
    nada.
    """
    total = session.scalar(
        select(func.coalesce(func.sum(Cheque.importe), 0)).where(
            Cheque.org_id == org_id, Cheque.estado == EN_CARTERA
        )
    )
    return Decimal(total or 0)


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


#: Cómo se nombra cada forma cuando se le habla a una persona. `efectivo` es "el efectivo" y no
#: "el cajón" porque es la palabra que usa el resto de la UI.
_NOMBRE_FORMA = {
    "efectivo": "El efectivo",
    "cheque": "La cartera de cheques",
    "transferencia": "El saldo por transferencias",
    "tarjeta": "El saldo por tarjeta",
}


def advertencias_de_saldo(
    session: Session, org_id: UUID, *, formas: Iterable[str] | None = None
) -> list[str]:
    """Un mensaje por cada forma cuyo saldo quedó en NEGATIVO. Advierte; no bloquea.

    Un saldo negativo es **físicamente imposible**: si el cajón dice −8.500, nadie sacó plata que no
    estaba — alguien cargó mal, o falta cargar un ingreso. Es información valiosa y por eso se dice.

    ## Por qué advertir y no bloquear

    Misma razón que el límite de crédito: **no hay roles ni mecanismo de override**. Un bloqueo duro
    deja el mostrador parado cuando el que puede autorizar no está, y el resultado real de eso no es
    que la operación no ocurra — es que ocurre fuera del sistema, que es peor. Cuando existan roles
    (Fase 3) se puede revisar.

    Que no bloquee es parte del contrato: **el movimiento se escribe igual**, y el caller decide qué
    hacer con el texto. Nunca lanza.

    `formas` acota el chequeo a las que la operación tocó, para no avisar de un negativo viejo que
    no tiene nada que ver con lo que la persona acaba de hacer. Sin argumento revisa todas, que es
    lo que sirve para una pantalla.
    """
    saldos = saldo_por_forma(session, org_id)
    a_revisar = sorted(set(formas)) if formas is not None else sorted(saldos)

    return [
        f"{_NOMBRE_FORMA.get(forma, forma)} quedó en {saldos[forma]:,.2f}. "
        "Un saldo negativo no puede pasar en la realidad: revisá si falta cargar un ingreso."
        for forma in a_revisar
        if saldos.get(forma, Decimal("0")) < 0
    ]


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
