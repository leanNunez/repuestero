from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.catalogo.models import Articulo
from app.compatibilidad.models import ArticuloAplicacion, Vehiculo

ORIGENES_VALIDOS = frozenset({"manual", "catalogo_proveedor", "extraido_ia"})


def crear_vehiculo(
    session: Session,
    org_id: UUID,
    *,
    marca: str,
    modelo: str,
    anio_desde: int | None = None,
    anio_hasta: int | None = None,
    motor: str | None = None,
    version: str | None = None,
) -> Vehiculo:
    vehiculo = Vehiculo(
        org_id=org_id,
        marca=marca,
        modelo=modelo,
        anio_desde=anio_desde,
        anio_hasta=anio_hasta,
        motor=motor,
        version=version,
    )
    session.add(vehiculo)
    session.flush()
    return vehiculo


def buscar_vehiculo(
    session: Session, org_id: UUID, *, marca: str, modelo: str, anio: int | None = None
) -> list[Vehiculo]:
    stmt = select(Vehiculo).where(
        Vehiculo.org_id == org_id,
        Vehiculo.marca.ilike(marca),
        Vehiculo.modelo.ilike(modelo),
    )
    if anio is not None:
        stmt = stmt.where(
            (Vehiculo.anio_desde.is_(None)) | (Vehiculo.anio_desde <= anio),
            (Vehiculo.anio_hasta.is_(None)) | (Vehiculo.anio_hasta >= anio),
        )
    return list(session.scalars(stmt))


def declarar_aplicacion(
    session: Session,
    org_id: UUID,
    *,
    articulo_id: int,
    vehiculo_id: int,
    origen: str = "manual",
    confirmado: bool = False,
    nota: str | None = None,
) -> ArticuloAplicacion:
    """Declara que un repuesto sirve para un vehículo.

    `origen` + `confirmado` NO son adorno. Cuando la compatibilidad la infiere un LLM a
    partir de la descripción, entra como sugerencia sin confirmar. Mezclar dato inferido
    con dato verificado es la forma más rápida de que el del mostrador deje de creerle al
    sistema — y una vez que dejó de creerle, no vuelve.
    """
    if origen not in ORIGENES_VALIDOS:
        raise ValueError(f"Origen inválido: {origen!r}. Válidos: {sorted(ORIGENES_VALIDOS)}")

    if origen == "extraido_ia" and confirmado:
        raise ValueError("Lo que infiere la IA entra sin confirmar. Lo confirma un humano.")

    aplicacion = ArticuloAplicacion(
        org_id=org_id,
        articulo_id=articulo_id,
        vehiculo_id=vehiculo_id,
        origen=origen,
        confirmado=confirmado,
        nota=nota,
    )
    session.add(aplicacion)
    session.flush()
    return aplicacion


def repuestos_para_vehiculo(
    session: Session, org_id: UUID, *, vehiculo_id: int, solo_confirmados: bool = False
) -> list[Articulo]:
    stmt = (
        select(Articulo)
        .join(ArticuloAplicacion, ArticuloAplicacion.articulo_id == Articulo.id)
        .where(
            Articulo.org_id == org_id,
            ArticuloAplicacion.vehiculo_id == vehiculo_id,
            Articulo.activo.is_(True),
        )
        .order_by(Articulo.detalle)
    )
    if solo_confirmados:
        stmt = stmt.where(ArticuloAplicacion.confirmado.is_(True))

    return list(session.scalars(stmt))
