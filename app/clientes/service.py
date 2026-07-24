import re
from decimal import Decimal
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.clientes.models import Cliente

_CUIT_RE = re.compile(r"^\d{2}-\d{8}-\d$")
_PESOS_CUIT = (5, 4, 3, 2, 7, 6, 5, 4, 3, 2)


def cuit_valido(cuit: str) -> bool:
    """Valida formato y dígito verificador (módulo 11).

    El legacy guardaba el CUIT como texto libre y nunca lo validaba. Resultado: campos
    basura que después rompen la factura electrónica, cuando ya es tarde y el cliente
    está esperando en el mostrador. Se valida en la puerta de entrada, no en la salida.
    """
    if not _CUIT_RE.match(cuit):
        return False

    digitos = [int(d) for d in cuit.replace("-", "")]
    suma = sum(d * p for d, p in zip(digitos[:10], _PESOS_CUIT, strict=True))
    resto = suma % 11
    verificador = 0 if resto == 0 else 11 - resto
    verificador = 9 if verificador == 10 else verificador

    return verificador == digitos[10]


def crear_cliente(
    session: Session,
    org_id: UUID,
    *,
    codigo: str,
    denominacion: str,
    cuit: str | None = None,
    cond_fiscal: str = "CONSUMIDOR_FINAL",
    limite_cta_cte: Decimal = Decimal("0"),
    telefono: str | None = None,
    email: str | None = None,
    direccion: str | None = None,
) -> Cliente:
    if cuit and not cuit_valido(cuit):
        raise ValueError(f"CUIT inválido: {cuit}")

    cliente = Cliente(
        org_id=org_id,
        codigo=codigo,
        denominacion=denominacion,
        cuit=cuit,
        cond_fiscal=cond_fiscal,
        limite_cta_cte=limite_cta_cte,
        telefono=telefono,
        email=email,
        direccion=direccion,
    )
    session.add(cliente)
    session.flush()
    return cliente


def obtener_cliente(session: Session, org_id: UUID, codigo: str) -> Cliente | None:
    return session.scalar(select(Cliente).where(Cliente.org_id == org_id, Cliente.codigo == codigo))


def obtener_cliente_por_id(session: Session, org_id: UUID, cliente_id: int) -> Cliente | None:
    """Por id, no por código. Lo necesita la cuenta corriente: el listado devuelve ids y el
    extracto se pide por id, mientras que las cobranzas siguen resolviendo por código."""
    return session.scalar(select(Cliente).where(Cliente.org_id == org_id, Cliente.id == cliente_id))


def listar_clientes(session: Session, org_id: UUID, *, limite: int = 50) -> list[Cliente]:
    return list(
        session.scalars(
            select(Cliente)
            .where(Cliente.org_id == org_id, Cliente.activo.is_(True))
            .order_by(Cliente.denominacion)
            .limit(limite)
        )
    )
