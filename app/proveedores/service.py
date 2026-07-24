from decimal import Decimal
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.proveedores.models import ArticuloProveedor, Proveedor


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


def listar_proveedores(session: Session, org_id: UUID, *, limite: int = 50) -> list[Proveedor]:
    return list(
        session.scalars(
            select(Proveedor)
            .where(Proveedor.org_id == org_id, Proveedor.activo.is_(True))
            .order_by(Proveedor.razon_social)
            .limit(limite)
        )
    )


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
    """
    proveedor = obtener_proveedor(session, org_id, codigo)
    if proveedor is not None:
        if cuit and not proveedor.cuit:
            proveedor.cuit = cuit
            session.flush()
        return proveedor

    return crear_proveedor(session, org_id, codigo=codigo, razon_social=razon_social, cuit=cuit)


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
