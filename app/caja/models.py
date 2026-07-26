from datetime import date, datetime
from decimal import Decimal
from uuid import UUID

from sqlalchemy import BigInteger, Boolean, Date, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.core.base import Base, BigIntPk, Money2, OrgMixin


class CajaMovimiento(Base, OrgMixin):
    """Libro del dinero. APPEND-ONLY, saldo como VISTA (`CajaSaldo`).

    Misma lección que `CtaCteMovimiento`, en la tabla donde más caro sale olvidarla: el saldo NO
    es una columna. Un error se corrige con el movimiento contrario, nunca editando el pasado —
    y el trigger de la 0011 lo hace cumplir.

    Dos columnas `ingreso`/`egreso` en vez de un importe con signo, igual que el ledger de cuenta
    corriente. Un signo invita a sumarlo mal en un reporte; dos columnas hacen la vista trivial.

    ## Derivado vs manual

    `ref_tipo`/`ref_id` en NULL = lo cargó una persona. Cargados = lo emitió un documento (un
    recibo, una orden de pago, la transición de un cheque) y nadie lo tipeó.

    **Si hay documento, caja no se toca a mano.** El endpoint de carga manual solo acepta los
    conceptos de `CONCEPTOS_MANUALES`; sin esa reja, alguien podría cargar la cobranza a mano
    ADEMÁS del recibo que ya la generó, y la caja diría el doble de lo que hay en el cajón.

    ## `forma` como dimensión, no como tabla aparte

    "La caja física" es este mismo libro filtrado por `forma='efectivo'`. Lo que entró por
    transferencia o tarjeta convive acá con otra forma, que es para lo que
    `app/core/formas_pago.py` dice existir.
    """

    __tablename__ = "caja_movimientos"

    id: Mapped[BigIntPk]
    fecha: Mapped[date] = mapped_column(Date, server_default=func.current_date())
    ingreso: Mapped[Money2] = mapped_column(default=Decimal("0"))
    egreso: Mapped[Money2] = mapped_column(default=Decimal("0"))
    #: 'efectivo' | 'cheque' | 'transferencia' | 'tarjeta' (`app.core.formas_pago`)
    forma: Mapped[str] = mapped_column(String(20))
    #: Ver `app.core.conceptos_caja`. La base impone que el concepto sea coherente con el lado:
    #: un 'gasto' no puede venir como ingreso.
    concepto: Mapped[str] = mapped_column(String(30))
    detalle: Mapped[str | None] = mapped_column(String(200))
    #: 'recibo' | 'orden_pago' | 'cheque', o NULL si es manual. Sin FK: apuntan a tablas
    #: distintas, igual que en los dos ledgers de cuenta corriente.
    ref_tipo: Mapped[str | None] = mapped_column(String(20))
    ref_id: Mapped[int | None] = mapped_column(BigInteger)
    creado_en: Mapped[datetime] = mapped_column(server_default=func.now())
    creado_por: Mapped[UUID | None]


class CajaSaldo(Base):
    """VISTA: saldo = SUM(ingreso) - SUM(egreso) POR FORMA. Nunca una columna mutable.

    `security_invoker = true` es OBLIGATORIO: sin eso la vista corre con los permisos de su owner
    y SALTEA el RLS de `caja_movimientos`, dejando a un tenant ver la caja de otro.
    `info={"is_view": True}` la excluye del autogenerate de Alembic (env.py::include_object).

    Entidad de SOLO LECTURA. Una forma sin movimientos NO aparece acá (saldo 0 implícito), así
    que el service tiene que tratar la ausencia de fila como cero — igual que `ClienteSaldo`.
    """

    __tablename__ = "caja_saldo"
    __table_args__ = {"info": {"is_view": True}}

    org_id: Mapped[UUID] = mapped_column(primary_key=True)
    forma: Mapped[str] = mapped_column(String(20), primary_key=True)
    saldo: Mapped[Money2]


class Cheque(Base, OrgMixin):
    """Un cheque de la cartera. **La única entidad mutable del módulo**, y es a propósito.

    Un cheque cambia de estado por naturaleza: entra a cartera, se deposita, se cobra o vuelve
    rechazado. Eso es el ciclo de vida de un papel, no un hecho contable.

    La regla del proyecto se cumple igual, en el lugar correcto: **la plata no muta**. Cada
    transición que mueve dinero escribe una fila NUEVA en `CajaMovimiento`. El estado es del
    papel; el dinero es del libro. Por eso la 0011 revoca DELETE pero no UPDATE: un cheque que
    existió no desaparece — se marca rechazado o entregado.

    `banco`, `numero`, `fecha_emision` y `fecha_cobro` son NULLABLE porque al derivar el cheque
    desde un recibo TODAVÍA no se conocen: un renglón de forma de pago solo trae `forma` y
    `monto`. Completarlos es tarea de la pantalla de cartera. Llevarlos en el payload del recibo
    es una mejora posterior — cambiaría un contrato que se acaba de estabilizar.
    """

    __tablename__ = "cheques"

    id: Mapped[BigIntPk]
    #: 'recibido' (me lo dio un cliente) | 'emitido' (lo firmé yo, va a un proveedor)
    origen: Mapped[str] = mapped_column(String(10))
    importe: Mapped[Money2]
    #: 'en_cartera' | 'depositado' | 'cobrado' | 'rechazado' | 'entregado'. Las transiciones
    #: VÁLIDAS las impone el service: un CHECK no puede mirar el estado anterior sin un trigger,
    #: y la máquina de estados es política de dominio, no del esquema.
    estado: Mapped[str] = mapped_column(String(15), server_default="en_cartera")
    banco: Mapped[str | None] = mapped_column(String(80))
    numero: Mapped[str | None] = mapped_column(String(40))
    fecha_emision: Mapped[date | None] = mapped_column(Date)
    #: Desde cuándo se puede cobrar. Es LO que hace útil a la cartera: sin esto no se puede
    #: responder "qué cheques puedo depositar esta semana".
    fecha_cobro: Mapped[date | None] = mapped_column(Date)
    conciliado: Mapped[bool] = mapped_column(Boolean, server_default="false")
    fecha_conciliacion: Mapped[date | None] = mapped_column(Date)
    #: 'recibo' | 'orden_pago': de qué documento salió.
    ref_tipo: Mapped[str | None] = mapped_column(String(20))
    ref_id: Mapped[int | None] = mapped_column(BigInteger)
    creado_en: Mapped[datetime] = mapped_column(server_default=func.now())
    creado_por: Mapped[UUID | None]
