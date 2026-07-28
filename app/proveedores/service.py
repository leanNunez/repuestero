from decimal import Decimal
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.cuit import cuit_valido
from app.core.numeracion import asignar_numero
from app.proveedores.models import ArticuloProveedor, Proveedor

#: Prefijo de los códigos que genera el sistema. El resto de los proveedores entra con su código
#: de afuera: el importador de Paradox trae el legacy, y `obtener_o_crear_proveedor` toma el que
#: sale de un remito escaneado (`app/ingesta_visual/service.py`). Los tres comparten
#: `uq_proveedores_org_codigo`, así que sin prefijo un alta desde la app puede chocar contra un
#: código que salió de un OCR y quedar bloqueada sin arreglo posible.
PREFIJO_CODIGO = "PRV-"

#: Ancho del contador. Con relleno de ceros el orden alfabético coincide con el cronológico.
_ANCHO_CODIGO = 6


def crear_proveedor(
    session: Session,
    org_id: UUID,
    *,
    codigo: str,
    razon_social: str,
    cuit: str | None = None,
    telefono: str | None = None,
    email: str | None = None,
) -> Proveedor:
    if cuit and not cuit_valido(cuit):
        # La reja va puesta acá y no solo en el borde HTTP: ni el importador de Paradox ni la
        # ingesta de remitos pasan por FastAPI, y son justo los dos caminos por los que entra
        # un CUIT que nadie tipeó.
        raise ValueError(f"CUIT inválido: {cuit}")

    proveedor = Proveedor(
        org_id=org_id,
        codigo=codigo,
        razon_social=razon_social,
        cuit=cuit,
        telefono=telefono,
        email=email,
    )
    session.add(proveedor)
    session.flush()
    return proveedor


def obtener_proveedor(session: Session, org_id: UUID, codigo: str) -> Proveedor | None:
    return session.scalar(
        select(Proveedor).where(Proveedor.org_id == org_id, Proveedor.codigo == codigo)
    )


def obtener_proveedor_por_id(session: Session, org_id: UUID, proveedor_id: int) -> Proveedor | None:
    """Por id, no por código. Lo necesita la cuenta corriente: el listado devuelve ids y el
    extracto se pide por id, mientras que los pagos siguen resolviendo por código."""
    return session.scalar(
        select(Proveedor).where(Proveedor.org_id == org_id, Proveedor.id == proveedor_id)
    )


def generar_codigo(session: Session, org_id: UUID) -> str:
    """Próximo código correlativo de la org, con el formato `PRV-000001`.

    Reutiliza el numerador de comprobantes: `asignar_numero` ya resuelve el `SELECT ... FOR UPDATE`
    que serializa a dos personas dando de alta al mismo tiempo. Numeración por lock, nunca
    `Max(id)+1`. `pto_venta=0` es convencional: un proveedor no tiene punto de venta.
    """
    numero = asignar_numero(session, org_id, tipo="PRV", pto_venta=0)
    return f"{PREFIJO_CODIGO}{numero:0{_ANCHO_CODIGO}d}"


def alta_proveedor(
    session: Session,
    org_id: UUID,
    *,
    razon_social: str,
    cuit: str | None = None,
    telefono: str | None = None,
    email: str | None = None,
) -> Proveedor:
    """Alta desde la app: igual que `crear_proveedor`, pero el código lo genera el sistema.

    `crear_proveedor` se queda como está porque el importador y la ingesta de remitos la llaman
    con un código que viene de afuera y hay que respetar tal cual. Dos puertas a propósito: una
    para lo que llega con identidad propia, otra para lo que nace acá.
    """
    return crear_proveedor(
        session,
        org_id,
        codigo=generar_codigo(session, org_id),
        razon_social=razon_social,
        cuit=cuit,
        telefono=telefono,
        email=email,
    )


def listar_proveedores(
    session: Session,
    org_id: UUID,
    *,
    buscar: str | None = None,
    limite: int = 50,
    offset: int = 0,
) -> tuple[list[Proveedor], int]:
    """Página del padrón + total del resultado filtrado. Espeja `clientes.listar_clientes`.

    Antes devolvía los primeros 50 por orden alfabético y nada más, que es lo que dejaba a la
    pantalla de compras sin poder elegir un proveedor del fondo del abecedario.

    El filtro por `org_id` es explícito aunque RLS ya lo garantice: RLS es la red de seguridad,
    no el filtro primario.
    """
    filtros = [Proveedor.org_id == org_id, Proveedor.activo.is_(True)]
    if buscar:
        patron = f"%{buscar}%"
        filtros.append(
            Proveedor.razon_social.ilike(patron)
            | Proveedor.codigo.ilike(patron)
            | Proveedor.cuit.ilike(patron)
        )

    total = session.scalar(select(func.count()).select_from(Proveedor).where(*filtros)) or 0

    # `codigo` de desempate: sin un segundo criterio estable la paginación deriva y una fila
    # puede salir en dos páginas y faltar en otra.
    items = session.scalars(
        select(Proveedor)
        .where(*filtros)
        .order_by(Proveedor.razon_social, Proveedor.codigo)
        .limit(limite)
        .offset(offset)
    )
    return list(items), total


def obtener_o_crear_proveedor(
    session: Session,
    org_id: UUID,
    *,
    codigo: str,
    razon_social: str,
    cuit: str | None = None,
) -> Proveedor:
    """El proveedor de un remito puede o no existir todavía. Esto resuelve las dos.

    Si ya existe NO se pisa la razón social: el nombre que leyó un OCR de un papel no es
    mejor dato que el que ya está cargado en el sistema. Solo se completa el CUIT si el
    registro no lo tenía — eso es agregar información, no reemplazarla.

    **Un CUIT que no valida se DESCARTA, no rompe la ingesta.** Acá el dato no lo tipeó nadie:
    lo leyó un OCR de un papel que puede estar arrugado, y el CUIT es información secundaria
    del remito. Frenar la carga entera por un dígito mal leído sería cambiar un campo vacío por
    un remito que no entra. Guardarlo mal es peor todavía: un CUIT a medias parece un dato, y
    el día que se emita un comprobante contra él nadie va a saber de dónde salió.
    """
    cuit_limpio = cuit if (cuit and cuit_valido(cuit)) else None

    proveedor = obtener_proveedor(session, org_id, codigo)
    if proveedor is not None:
        if cuit_limpio and not proveedor.cuit:
            proveedor.cuit = cuit_limpio
            session.flush()
        return proveedor

    return crear_proveedor(
        session, org_id, codigo=codigo, razon_social=razon_social, cuit=cuit_limpio
    )


def vincular_articulo(
    session: Session,
    org_id: UUID,
    *,
    articulo_id: int,
    proveedor_id: int,
    codigo_proveedor: str | None = None,
    costo: Decimal = Decimal("0"),
    es_preferido: bool = False,
) -> ArticuloProveedor:
    """Insert-only: re-vincular el mismo (articulo, proveedor) viola uq_artprov. Para un
    vínculo que puede ya existir, usá `upsert_vinculo_articulo`."""
    vinculo = ArticuloProveedor(
        org_id=org_id,
        articulo_id=articulo_id,
        proveedor_id=proveedor_id,
        codigo_proveedor=codigo_proveedor,
        costo=costo,
        es_preferido=es_preferido,
    )
    session.add(vinculo)
    session.flush()
    return vinculo


def upsert_vinculo_articulo(
    session: Session,
    org_id: UUID,
    *,
    articulo_id: int,
    proveedor_id: int,
    codigo_proveedor: str | None = None,
    costo: Decimal = Decimal("0"),
    es_preferido: bool = False,
) -> ArticuloProveedor:
    """Vincula un artículo con un proveedor, exista o no el vínculo.

    El `codigo_proveedor` del renglón de un remito (el código con el que el proveedor
    llama a esa pieza, distinto del propio) es justo el dato que esta tabla existe para
    guardar: es lo que después permite reconocer el artículo en el próximo remito.

    Solo pisa `codigo_proveedor` si viene con algo. Que un remito no lo traiga no es razón
    para borrar el que ya estaba.
    """
    vinculo = session.scalar(
        select(ArticuloProveedor).where(
            ArticuloProveedor.org_id == org_id,
            ArticuloProveedor.articulo_id == articulo_id,
            ArticuloProveedor.proveedor_id == proveedor_id,
        )
    )

    if vinculo is None:
        return vincular_articulo(
            session,
            org_id,
            articulo_id=articulo_id,
            proveedor_id=proveedor_id,
            codigo_proveedor=codigo_proveedor,
            costo=costo,
            es_preferido=es_preferido,
        )

    vinculo.costo = costo
    if codigo_proveedor:
        vinculo.codigo_proveedor = codigo_proveedor
    if es_preferido:
        vinculo.es_preferido = True
    session.flush()
    return vinculo
