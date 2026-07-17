from decimal import ROUND_HALF_UP, Decimal
from uuid import UUID

from sqlalchemy import select, text
from sqlalchemy.orm import Session

from app.catalogo.models import Articulo, ArticuloPrecio, ListaPrecio
from app.catalogo.schemas import ArticuloActualizar, ArticuloCrear, ListaPrecioCrear
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


def actualizar_articulo(
    session: Session, org_id: UUID, *, articulo: Articulo, datos: ArticuloActualizar
) -> Articulo:
    """Update parcial. Solo pisa los campos que el caller seteó explícitamente.

    `exclude_unset=True` es la clave: distingue "no me lo mandaste" de "mandámelo en None".
    Sin eso, actualizar el costo desde un remito borraría la marca y el rubro del artículo.

    NO toca dos columnas, por razones opuestas:
    - `busqueda` es `Computed`: Postgres la regenera sola en el UPDATE. Tocarla es un error.
    - `embedding` NO se invalida acá aunque el detalle cambie. Ver `asegurar_embeddings`:
      ponerlo en None abriría una ventana en la que el artículo desaparece de la búsqueda
      semántica hasta que corra un batch. El caller re-embebe en la misma transacción.
    """
    for campo, valor in datos.model_dump(exclude_unset=True).items():
        setattr(articulo, campo, valor)
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
    precio: Decimal,
    margen: Decimal | None = None,
) -> ArticuloPrecio:
    """Insert-only: re-fijar el precio de un (articulo, lista) viola uq_precio_articulo_lista.

    Para actualizar un precio existente usá `upsert_precio`. Esta queda porque el importador
    la usa sobre una base vacía, donde el insert directo es lo correcto.
    """
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


def listar_precios_de_articulo(
    session: Session, org_id: UUID, articulo_id: int
) -> list[tuple[ArticuloPrecio, ListaPrecio]]:
    """Los precios de un artículo con su lista. Devuelve ambos porque quien muestra un
    precio necesita decir de qué lista es ('Mostrador', 'Mayorista'), no un lista_id."""
    filas = session.execute(
        select(ArticuloPrecio, ListaPrecio)
        .join(ListaPrecio, ListaPrecio.id == ArticuloPrecio.lista_id)
        .where(ArticuloPrecio.org_id == org_id, ArticuloPrecio.articulo_id == articulo_id)
        .order_by(ListaPrecio.codigo)
    ).all()
    return [(precio, lista) for precio, lista in filas]


def upsert_precio(
    session: Session,
    org_id: UUID,
    *,
    articulo_id: int,
    lista_id: int,
    precio: Decimal,
    margen: Decimal | None = None,
) -> ArticuloPrecio:
    """Fija el precio de un (articulo, lista), exista o no la fila.

    Es lo que `fijar_precio` no puede hacer: aquella es insert-only y revienta contra
    `uq_precio_articulo_lista` al re-fijar. Toma ids en vez de objetos ORM, como el resto
    de los services del proyecto (`registrar_movimiento`, `vincular_articulo`).

    El filtro por org_id es explícito aunque `uq_precio_articulo_lista` NO esté scopeado
    por org: la unicidad la garantiza (articulo_id, lista_id), pero este SELECT igual se
    apoya en las dos barreras — el where del código y RLS en el motor.
    """
    fila = session.scalar(
        select(ArticuloPrecio).where(
            ArticuloPrecio.org_id == org_id,
            ArticuloPrecio.articulo_id == articulo_id,
            ArticuloPrecio.lista_id == lista_id,
        )
    )

    if fila is None:
        fila = ArticuloPrecio(
            org_id=org_id,
            articulo_id=articulo_id,
            lista_id=lista_id,
            precio=precio,
            margen=margen,
        )
        session.add(fila)
    else:
        fila.precio = precio
        if margen is not None:
            fila.margen = margen

    session.flush()
    return fila


def calcular_precio(costo: Decimal, margen: Decimal) -> Decimal:
    """Precio de venta a partir del costo y el margen. MARKUP SOBRE COSTO: costo × (1 + m/100).

    Con costo 100 y margen 40 devuelve 140, NO 166,67 (eso sería margen sobre el precio de
    venta). No es una elección estética: es la fórmula que ya usan los datos del sistema
    (ver seeds/generar_demo.py, que genera los precios así). Si esto cambiara, todos los
    precios recalculados dejarían de cuadrar con los cargados.

    El `quantize` a centavos es obligatorio, no cosmético: `costo` es numeric(14,4) y
    `precio` es numeric(14,2). Sin redondear acá, Postgres redondea al guardar con su
    propia regla y el precio que se le mostró al humano no es el que quedó en la base.
    """
    return (costo * (Decimal(1) + margen / Decimal(100))).quantize(
        Decimal("0.01"), rounding=ROUND_HALF_UP
    )


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
        a.id: a for a in session.scalars(select(Articulo).where(Articulo.id.in_(puntajes)))
    }
    # Se respeta el orden por score del SQL (session.scalars no lo garantiza).
    return [(articulos[i], puntajes[i]) for i in puntajes]


# --------------------------------------------------------------------------- indexado


def texto_para_embedding(articulo: Articulo) -> str:
    """El texto que representa al artículo para el embedding. Mismos campos que el tsvector FTS,
    para que ambos arms 'vean' lo mismo."""
    partes = [articulo.detalle, articulo.marca, articulo.rubro, articulo.codigo]
    return " ".join(p for p in partes if p)


def asegurar_embeddings(session: Session, org_id: UUID, *, articulos: list[Articulo]) -> int:
    """Re-embebe AHORA una lista corta y conocida de artículos, en la misma transacción.

    Es la contraparte interactiva de `reindexar_embeddings`, y existe por dos motivos:

    1. **Un artículo recién creado sería invisible a la búsqueda semántica.** El brazo
       vectorial filtra `embedding is not null`, así que hasta que corriera un batch el
       artículo solo aparecería por el brazo léxico (`busqueda` sí la genera Postgres en
       el INSERT). Quien carga un producto y lo busca a los diez segundos no lo encontraría.
    2. **Un artículo editado conservaría un embedding MENTIROSO para siempre.**
       `reindexar_embeddings` solo llena NULLs: si cambia el `detalle`, su vector viejo
       nunca se recalcula. Este es un bug latente que este camino además tapa.

    ¿Y por qué no rompe la razón por la que el indexado está fuera del hot path? Porque esa
    razón es el cold-load del modelo (~120MB), y el proceso de la API YA lo pagó al arrancar
    (`main.py` llama a `precargar_embeddings()` en el startup, y el modelo queda cacheado con
    `lru_cache`). Lo que queda es embeber un puñado de textos cortos: decenas de ms, una vez,
    en un endpoint donde el humano ya esperó varios segundos de OCR. `reindexar_embeddings`
    sigue siendo lo correcto para el CLI de importación masiva, que sí paga el cold-load.

    A diferencia de aquella, esta SÍ toma org_id: no barre la base buscando pendientes, opera
    sobre objetos que el caller ya tiene en la mano.
    """
    if not articulos:
        return 0

    vectores = embed_passages([texto_para_embedding(a) for a in articulos])
    for articulo, vector in zip(articulos, vectores, strict=True):
        articulo.embedding = vector
    session.flush()
    return len(articulos)


def reindexar_embeddings(session: Session, *, lote: int = 256) -> int:
    """Genera y guarda el embedding de todos los articulos que aún no lo tienen. Por lotes.

    Fuera del hot path a propósito: cargar el modelo y embeber es caro. Se corre una vez después
    de importar (ver catalogo/reindex.py), no en cada alta de artículo.

    OJO: solo llena NULLs y NO filtra por org (depende del rol/RLS de la sesión — está pensada
    para el CLI, que corre como owner y bypassea RLS para indexar todos los tenants de una).
    Para el camino interactivo, y para re-embeber un artículo EDITADO, usá `asegurar_embeddings`.
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
