from decimal import Decimal
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.inventario.models import Deposito, Stock, StockMovimiento

MOTIVOS_VALIDOS = frozenset({"inicial", "compra", "venta", "ajuste", "transferencia"})


def crear_deposito(session: Session, org_id: UUID, *, codigo: str, nombre: str) -> Deposito:
    deposito = Deposito(org_id=org_id, codigo=codigo, nombre=nombre)
    session.add(deposito)
    session.flush()
    return deposito


def obtener_deposito(session: Session, org_id: UUID, codigo: str) -> Deposito | None:
    return session.scalar(
        select(Deposito).where(Deposito.org_id == org_id, Deposito.codigo == codigo)
    )


def registrar_movimiento(
    session: Session,
    org_id: UUID,
    *,
    articulo_id: int,
    deposito_id: int,
    cantidad: Decimal,
    motivo: str,
    ref_tipo: str | None = None,
    ref_id: int | None = None,
    usuario_id: UUID | None = None,
) -> StockMovimiento:
    """ÚNICA puerta de entrada al stock. No existe forma legítima de tocarlo sin pasar por acá.

    La cantidad va con signo: positivo entra, negativo sale. Un ajuste que corrige un error
    no borra ni edita el movimiento equivocado — agrega el contra-movimiento. El kardex es
    append-only y la base lo hace cumplir con un trigger, no confía en que nos portemos bien.
    """
    if motivo not in MOTIVOS_VALIDOS:
        raise ValueError(f"Motivo inválido: {motivo!r}. Válidos: {sorted(MOTIVOS_VALIDOS)}")

    if cantidad == 0:
        raise ValueError("Un movimiento de stock con cantidad 0 no significa nada")

    movimiento = StockMovimiento(
        org_id=org_id,
        articulo_id=articulo_id,
        deposito_id=deposito_id,
        cantidad=cantidad,
        motivo=motivo,
        ref_tipo=ref_tipo,
        ref_id=ref_id,
        creado_por=usuario_id,
    )
    session.add(movimiento)
    session.flush()
    return movimiento


def stock_de_articulo(session: Session, org_id: UUID, articulo_id: int) -> list[Stock]:
    """Lee la VISTA. Nunca hay un número guardado que pueda contradecir al kardex."""
    return list(
        session.scalars(
            select(Stock).where(Stock.org_id == org_id, Stock.articulo_id == articulo_id)
        )
    )
