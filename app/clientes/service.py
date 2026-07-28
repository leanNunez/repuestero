import re
from decimal import Decimal
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.clientes.models import Cliente
from app.core.cond_fiscal import COND_FISCAL_POR_DEFECTO, CONDICIONES_FISCALES
from app.core.numeracion import asignar_numero

_CUIT_RE = re.compile(r"^\d{2}-\d{8}-\d$")
_PESOS_CUIT = (5, 4, 3, 2, 7, 6, 5, 4, 3, 2)

#: Prefijo de los códigos que genera el sistema. Los importados de Paradox entran con su código
#: legacy tal cual (`app/importador/loader.py`), del estilo `C001`, y comparten el mismo
#: `uq_clientes_org_codigo`. El prefijo garantiza que lo generado nunca choque con lo importado.
PREFIJO_CODIGO = "CLI-"

#: Ancho del contador. Con relleno de ceros el orden alfabético coincide con el cronológico, que es
#: como se lee la columna en el listado (`codigo` es `String(20)`, no un entero).
_ANCHO_CODIGO = 6


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
    cond_fiscal: str = COND_FISCAL_POR_DEFECTO,
    limite_cta_cte: Decimal = Decimal("0"),
    telefono: str | None = None,
    email: str | None = None,
    direccion: str | None = None,
) -> Cliente:
    if cuit and not cuit_valido(cuit):
        raise ValueError(f"CUIT inválido: {cuit}")

    if cond_fiscal not in CONDICIONES_FISCALES:
        # La reja va puesta dos veces a propósito: el importador NO pasa por el borde HTTP, así que
        # el `Literal` de Pydantic no lo alcanza. Acá el error dice qué se esperaba; sin esto, el
        # CHECK de la base lo frena igual pero con un IntegrityError ilegible.
        raise ValueError(
            f"Condición fiscal inválida: {cond_fiscal}. "
            f"Esperaba una de {sorted(CONDICIONES_FISCALES)}"
        )

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


def generar_codigo(session: Session, org_id: UUID) -> str:
    """Próximo código correlativo de la org, con el formato `CLI-000001`.

    Reutiliza el numerador de comprobantes: `asignar_numero` ya resuelve el `SELECT ... FOR UPDATE`
    que serializa a dos personas dando de alta al mismo tiempo. Es la regla no negociable del
    proyecto —numeración por lock, nunca `Max(id)+1`— y no hay motivo para escribirla otra vez.

    `pto_venta=0` es convencional: un cliente no tiene punto de venta. La clave del numerador es
    `(org_id, tipo, pto_venta)`, así que el 0 fijo deja una única fila `CLI` por organización.
    """
    numero = asignar_numero(session, org_id, tipo="CLI", pto_venta=0)
    return f"{PREFIJO_CODIGO}{numero:0{_ANCHO_CODIGO}d}"


def alta_cliente(
    session: Session,
    org_id: UUID,
    *,
    denominacion: str,
    cuit: str | None = None,
    cond_fiscal: str = COND_FISCAL_POR_DEFECTO,
    limite_cta_cte: Decimal = Decimal("0"),
    telefono: str | None = None,
    email: str | None = None,
    direccion: str | None = None,
) -> Cliente:
    """Alta desde la app: igual que `crear_cliente`, pero el código lo genera el sistema.

    `crear_cliente` se queda como está porque el importador la llama con el código legacy del
    Paradox, que hay que respetar tal cual. Las dos puertas conviven a propósito: una para lo que
    viene de afuera con identidad propia, otra para lo que nace acá.
    """
    cliente = crear_cliente(
        session,
        org_id,
        codigo=generar_codigo(session, org_id),
        denominacion=denominacion,
        cuit=cuit,
        cond_fiscal=cond_fiscal,
        limite_cta_cte=limite_cta_cte,
        telefono=telefono,
        email=email,
        direccion=direccion,
    )

    # Sin esto, el objeto queda con el Decimal que le pasamos —`Decimal("0")`— y no con el que la
    # base normalizó a `numeric(_, 2)`. El POST devolvería "0" y el GET del mismo cliente "0.00":
    # el mismo campo del mismo registro con dos representaciones según por dónde se lo pida.
    # Va acá y no en `crear_cliente` a propósito: el importador carga miles de filas y no puede
    # pagar un SELECT por cada una.
    session.refresh(cliente)
    return cliente


def obtener_cliente(session: Session, org_id: UUID, codigo: str) -> Cliente | None:
    return session.scalar(select(Cliente).where(Cliente.org_id == org_id, Cliente.codigo == codigo))


def obtener_cliente_por_id(session: Session, org_id: UUID, cliente_id: int) -> Cliente | None:
    """Por id, no por código. Lo necesita la cuenta corriente: el listado devuelve ids y el
    extracto se pide por id, mientras que las cobranzas siguen resolviendo por código."""
    return session.scalar(select(Cliente).where(Cliente.org_id == org_id, Cliente.id == cliente_id))


def listar_clientes(
    session: Session,
    org_id: UUID,
    *,
    buscar: str | None = None,
    limite: int = 50,
    offset: int = 0,
) -> tuple[list[Cliente], int]:
    """Página del padrón + total del resultado filtrado. Espeja `catalogo.listar_articulos`.

    Devuelve `(items, total)` y no una lista pelada porque sin el total el front no puede paginar:
    sabría qué está viendo pero no cuánto falta. Antes esto devolvía los primeros 50 por orden
    alfabético y nada más, así que un cliente recién dado de alta —o cualquiera de la mitad de
    abajo del abecedario— era invisible para la app: existía en la base y no había forma de
    llegar a él desde la pantalla.

    El filtro por `org_id` es explícito aunque RLS ya lo garantice: RLS es la red de seguridad,
    no el filtro primario.

    `buscar` mira denominación, código Y CUIT. El CUIT entra a propósito: en el mostrador el
    dato que llega escrito es el de la factura del cliente, no el código interno del sistema.
    """
    filtros = [Cliente.org_id == org_id, Cliente.activo.is_(True)]
    if buscar:
        patron = f"%{buscar}%"
        filtros.append(
            Cliente.denominacion.ilike(patron)
            | Cliente.codigo.ilike(patron)
            | Cliente.cuit.ilike(patron)
        )

    total = session.scalar(select(func.count()).select_from(Cliente).where(*filtros)) or 0

    # `codigo` de desempate: dos clientes pueden llamarse igual (dos sucursales de la misma
    # empresa) y sin un segundo criterio estable la paginación deriva — una fila se repetiría en
    # una página y faltaría en la otra, según cómo el motor resuelva el empate esa vez.
    items = session.scalars(
        select(Cliente)
        .where(*filtros)
        .order_by(Cliente.denominacion, Cliente.codigo)
        .limit(limite)
        .offset(offset)
    )
    return list(items), total
