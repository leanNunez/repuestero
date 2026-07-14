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
