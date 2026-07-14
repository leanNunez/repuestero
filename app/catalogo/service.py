from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.catalogo.models import Articulo, ArticuloPrecio, ListaPrecio
from app.catalogo.schemas import ArticuloCrear, ListaPrecioCrear


def listar_articulos(
    session: Session, org_id: UUID, *, buscar: str | None = None, limite: int = 50
) -> list[Articulo]:
    """Los filtros por org_id son explícitos A PROPÓSITO, aunque RLS ya los garantice.

    RLS es la RED DE SEGURIDAD, no el filtro primario. Si el día de mañana alguien corre
    esta query con un rol mal configurado, el `where` explícito la salva igual. Dos
    barreras independientes: una en el código, otra en el motor.
    """
    stmt = (
        select(Articulo)
        .where(Articulo.org_id == org_id, Articulo.activo.is_(True))
        .order_by(Articulo.codigo)
    )

    if buscar:
        patron = f"%{buscar}%"
        stmt = stmt.where(Articulo.detalle.ilike(patron) | Articulo.codigo.ilike(patron))

    return list(session.scalars(stmt.limit(limite)))


def obtener_articulo(session: Session, org_id: UUID, codigo: str) -> Articulo | None:
    return session.scalar(
        select(Articulo).where(Articulo.org_id == org_id, Articulo.codigo == codigo)
    )


def crear_articulo(session: Session, org_id: UUID, datos: ArticuloCrear) -> Articulo:
    articulo = Articulo(org_id=org_id, **datos.model_dump())
    session.add(articulo)
    session.flush()
    return articulo


def crear_lista_precio(session: Session, org_id: UUID, datos: ListaPrecioCrear) -> ListaPrecio:
    lista = ListaPrecio(org_id=org_id, **datos.model_dump())
    session.add(lista)
    session.flush()
    return lista


def obtener_lista_precio(session: Session, org_id: UUID, codigo: str) -> ListaPrecio | None:
    return session.scalar(
        select(ListaPrecio).where(ListaPrecio.org_id == org_id, ListaPrecio.codigo == codigo)
    )


def fijar_precio(
    session: Session,
    org_id: UUID,
    *,
    articulo: Articulo,
    lista: ListaPrecio,
    precio,
    margen=None,
) -> ArticuloPrecio:
    fila = ArticuloPrecio(
        org_id=org_id,
        articulo_id=articulo.id,
        lista_id=lista.id,
        precio=precio,
        margen=margen,
    )
    session.add(fila)
    session.flush()
    return fila
