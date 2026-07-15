from uuid import UUID

from sqlalchemy import select, text
from sqlalchemy.orm import Session

from app.catalogo.models import Articulo, ArticuloPrecio, ListaPrecio
from app.catalogo.schemas import ArticuloCrear, ListaPrecioCrear
from app.core.embeddings import embed_passages, embed_query


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


# --------------------------------------------------------------------------- búsqueda híbrida

#: Constante de RRF (Reciprocal Rank Fusion). 60 es el valor estándar del paper original: aplana
#: el peso de las posiciones altas para que ni el arm léxico ni el semántico domine solo.
_RRF_K = 60

#: Umbral de word_similarity para el matcheo difuso (typos). word_similarity —no similarity— mide
#: cuánto matchea la consulta contra la MEJOR parte del detalle, así "amortguador" pega contra
#: "AMORTIGUADOR TRASERO SADAR 30125" sin diluirse en las otras palabras.
_TRGM_MIN = 0.3

_BUSQUEDA_SQL = text(
    """
    with q as (
        -- tsquery en modo OR: matchea si CUALQUIER término pega, no todos. websearch_to_tsquery
        -- arma un query con '&' (AND), inútil para lenguaje natural ("necesito frenar el auto"
        -- no matchea ningún artículo). Reemplazar ' & ' por ' | ' sobre el texto YA parseado y
        -- stemmed por Postgres da el OR sin riesgo de inyección (Postgres hizo el parsing).
        select nullif(
                   replace(websearch_to_tsquery('spanish', :q)::text, ' & ', ' | '), ''
               )::tsquery as tsq
    ),
    kw as (  -- arm LÉXICO: full-text español (OR) + trigram tolerante a typos
        select a.id,
               row_number() over (
                   order by greatest(
                       ts_rank_cd(a.busqueda, q.tsq),
                       word_similarity(:q, a.detalle)
                   ) desc
               ) as rnk
        from articulos a, q
        where a.org_id = :org and a.activo
          and (a.busqueda @@ q.tsq or word_similarity(:q, a.detalle) >= :trgm)
        limit 50
    ),
    vec as (  -- arm SEMÁNTICO: distancia coseno sobre el embedding
        select id,
               row_number() over (order by embedding <=> cast(:qvec as vector)) as rnk
        from articulos
        where org_id = :org and activo and embedding is not null
        order by embedding <=> cast(:qvec as vector)
        limit 50
    )
    select coalesce(kw.id, vec.id) as id,
           coalesce(1.0 / (:k + kw.rnk), 0) + coalesce(1.0 / (:k + vec.rnk), 0) as score
    from kw
    full outer join vec on kw.id = vec.id
    order by score desc
    limit :limite
    """
)


def _vector_literal(vec: list[float]) -> str:
    """Formatea el vector como literal pgvector ('[..]') para castear en SQL sin adaptadores."""
    return "[" + ",".join(str(x) for x in vec) + "]"


def buscar_articulos(
    session: Session, org_id: UUID, *, q: str, limite: int = 20
) -> list[tuple[Articulo, float]]:
    """Búsqueda HÍBRIDA: fusiona un ranking léxico y uno semántico por RRF.

    El léxico encuentra lo que matchea por texto (y aguanta typos); el semántico encuentra lo
    que matchea por SIGNIFICADO ("algo para filtrar el aceite" → FILTRO DE ACEITE). Ninguno solo
    alcanza: keyword no entiende sinónimos, y el vector solo se pierde los códigos exactos. RRF
    los combina sin que uno tape al otro.

    El filtro por `org_id` es explícito además del RLS: dos barreras, igual que en el resto.
    """
    qvec = embed_query(q)
    filas = session.execute(
        _BUSQUEDA_SQL,
        {
            "q": q,
            "qvec": _vector_literal(qvec),
            "org": org_id,
            "trgm": _TRGM_MIN,
            "k": _RRF_K,
            "limite": limite,
        },
    ).all()
    if not filas:
        return []

    puntajes = {fila.id: float(fila.score) for fila in filas}
    articulos = {
        a.id: a
        for a in session.scalars(select(Articulo).where(Articulo.id.in_(puntajes)))
    }
    # Se respeta el orden por score del SQL (session.scalars no lo garantiza).
    return [(articulos[i], puntajes[i]) for i in puntajes]


# --------------------------------------------------------------------------- indexado

def texto_para_embedding(articulo: Articulo) -> str:
    """El texto que representa al artículo para el embedding. Mismos campos que el tsvector FTS,
    para que ambos arms 'vean' lo mismo."""
    partes = [articulo.detalle, articulo.marca, articulo.rubro, articulo.codigo]
    return " ".join(p for p in partes if p)


def reindexar_embeddings(session: Session, *, lote: int = 256) -> int:
    """Genera y guarda el embedding de todos los articulos que aún no lo tienen. Por lotes.

    Fuera del hot path a propósito: cargar el modelo y embeber es caro. Se corre una vez después
    de importar (ver catalogo/reindex.py), no en cada alta de artículo.
    """
    total = 0
    while True:
        pendientes = list(
            session.scalars(select(Articulo).where(Articulo.embedding.is_(None)).limit(lote))
        )
        if not pendientes:
            break
        vectores = embed_passages([texto_para_embedding(a) for a in pendientes])
        for articulo, vector in zip(pendientes, vectores, strict=True):
            articulo.embedding = vector
        session.flush()
        total += len(pendientes)
    return total
