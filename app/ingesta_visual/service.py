"""Orquestación de la ingesta visual. NO escribe SQL: compone los services de cada módulo.

Mismo rol que `app/importador/loader.py`, y por la misma razón: el dueño de `articulos` es
`catalogo`, y si este módulo insertara directo se convertiría en una segunda puerta al
catálogo — el agujero por donde entra la basura que el importador se cuida de no ser.

Este archivo tiene las dos mitades del HITL:
- `preparar_propuesta`: lee, compara, marca. NO escribe una sola fila.
- `confirmar`: escribe lo que el humano aprobó, todo o nada. (Slice 5)
"""

import logging
from decimal import Decimal
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.asistente import seguridad
from app.catalogo import service as catalogo
from app.catalogo.schemas import ArticuloActualizar, ArticuloCrear
from app.core.config import get_settings
from app.ingesta_visual import extractor, flags
from app.ingesta_visual.imagen import decodificar, hash_imagen
from app.ingesta_visual.models import RemitoProcesado
from app.ingesta_visual.schemas import (
    ConfirmarRequest,
    ConfirmarResponse,
    PrecioPreview,
    PropuestaResponse,
    RemitoExtraido,
    RenglonExtraido,
    RenglonPropuesta,
)
from app.inventario import service as inventario
from app.proveedores import service as proveedores

logger = logging.getLogger(__name__)


def _remito_ya_cargado(session: Session, org_id: UUID, imagen_hash: str) -> RemitoProcesado | None:
    return session.scalar(
        select(RemitoProcesado).where(
            RemitoProcesado.org_id == org_id,
            RemitoProcesado.imagen_hash == imagen_hash,
        )
    )


def _preview_de_precios(
    session: Session, org_id: UUID, *, articulo_id: int, costo_nuevo: Decimal
) -> tuple[list[PrecioPreview], bool, bool]:
    """Qué pasaría con cada lista si se confirma este costo.

    Devuelve (previews, tiene_listas, tiene_algun_margen). No escribe nada: es exactamente
    el mismo cálculo que hará `confirmar`, mostrado antes de hacerlo. Que el humano vea el
    número que va a quedar es la mitad del valor del HITL.
    """
    filas = catalogo.listar_precios_de_articulo(session, org_id, articulo_id)
    previews: list[PrecioPreview] = []
    tiene_margen = False

    for precio, lista in filas:
        nuevo = None
        if precio.margen is not None:
            tiene_margen = True
            nuevo = catalogo.calcular_precio(costo_nuevo, precio.margen)
        previews.append(
            PrecioPreview(
                lista_codigo=lista.codigo,
                lista_nombre=lista.nombre,
                precio_actual=precio.precio,
                margen=precio.margen,
                precio_nuevo=nuevo,
            )
        )

    return previews, bool(filas), tiene_margen


def _propuesta_de_renglon(
    session: Session,
    org_id: UUID,
    renglon: RenglonExtraido,
    *,
    duplicados: set[str],
    umbral: float,
) -> RenglonPropuesta:
    codigo = (renglon.codigo or "").strip()
    articulo = catalogo.obtener_articulo(session, org_id, codigo) if codigo else None
    es_alta = articulo is None

    previews: list[PrecioPreview] = []
    tiene_listas = tiene_margen = False
    if articulo is not None:
        previews, tiene_listas, tiene_margen = _preview_de_precios(
            session, org_id, articulo_id=articulo.id, costo_nuevo=renglon.costo_unitario
        )

    # El texto viene de una fuente NO confiable (un papel que trajo un tercero). Se escanea
    # para MARCAR, nunca para bloquear ni para sumar strikes: ver la nota en `preparar_propuesta`.
    sospechoso = seguridad.es_injection(renglon.descripcion)
    if sospechoso:
        logger.warning("Texto sospechoso en renglón de remito (org=%s, codigo=%r)", org_id, codigo)

    atencion = flags.flags_de_renglon(
        renglon,
        costo_actual=articulo.costo if articulo else None,
        tiene_listas=tiene_listas,
        tiene_margen=tiene_margen,
        es_alta=es_alta,
        duplicado=bool(codigo) and codigo in duplicados,
        texto_sospechoso=sospechoso,
        umbral_confianza=umbral,
    )

    return RenglonPropuesta(
        codigo=codigo or None,
        descripcion=renglon.descripcion,
        cantidad=renglon.cantidad,
        costo_unitario=renglon.costo_unitario,
        confianza=renglon.confianza,
        accion="alta" if es_alta else "actualizacion",
        articulo_id=articulo.id if articulo else None,
        detalle_actual=articulo.detalle if articulo else None,
        costo_actual=articulo.costo if articulo else None,
        precios=previews,
        atencion=atencion,
        incluir_sugerido=flags.incluir_por_defecto(atencion),
    )


def armar_propuesta(
    session: Session,
    org_id: UUID,
    *,
    extraido: RemitoExtraido,
    imagen_hash: str,
) -> PropuestaResponse:
    """Cruza lo extraído contra lo que el sistema ya sabe. Separada de `preparar_propuesta`
    para poder testear el cruce sin pasar por la imagen ni por el LLM."""
    umbral = get_settings().ingesta_umbral_confianza
    duplicados = flags.codigos_duplicados(extraido.renglones)

    renglones = [
        _propuesta_de_renglon(session, org_id, r, duplicados=duplicados, umbral=umbral)
        for r in extraido.renglones
    ]

    return PropuestaResponse(
        remito_hash=imagen_hash,
        ya_procesado=False,
        proveedor_nombre=extraido.proveedor_nombre,
        proveedor_cuit=extraido.proveedor_cuit,
        numero_remito=extraido.numero_remito,
        fecha=extraido.fecha,
        total_declarado=extraido.total_declarado,
        total_calculado=flags.total_calculado(extraido.renglones),
        renglones=renglones,
        advertencias=flags.advertencias_de_remito(extraido.renglones, extraido.total_declarado),
    )


def preparar_propuesta(
    session: Session, org_id: UUID, *, imagen_base64: str, mime: str
) -> PropuestaResponse:
    """Foto → propuesta. NO ESCRIBE NADA. Esa es toda la garantía de este endpoint.

    Sobre el prompt injection por imagen: el texto de un remito es una fuente no confiable
    (lo imprime un tercero). Se escanea cada descripción con el guard del asistente, pero
    solo para MARCAR el renglón — no se bloquea el remito ni se registran strikes contra la
    IP. El guard está calibrado para consultas en español y un código de repuesto raro es un
    falso positivo perfectamente plausible: banear a un usuario por lo que dice el papel de
    su proveedor sería un bug de producto, no una defensa.
    """
    datos = decodificar(imagen_base64, mime)
    h = hash_imagen(datos)

    # Cortar ANTES de llamar al modelo: cada llamada cuesta plata y este remito ya se cargó.
    ya = _remito_ya_cargado(session, org_id, h)
    if ya is not None:
        return PropuestaResponse(
            remito_hash=h,
            ya_procesado=True,
            procesado_en=ya.creado_en,
            numero_remito=ya.numero_remito,
            advertencias=["Este remito ya se cargó. No se volvió a leer la imagen."],
        )

    extraido = extractor.extraer(imagen_base64, mime)
    return armar_propuesta(session, org_id, extraido=extraido, imagen_hash=h)


# --------------------------------------------------------------------------- confirmar


class DatoInvalido(ValueError):
    """Algo del payload no existe o no cierra. El router lo traduce a un 422."""


def _recalcular_precios(
    session: Session, org_id: UUID, *, articulo_id: int, costo: Decimal
) -> tuple[int, bool]:
    """Recalcula los precios de venta con el margen de CADA lista. Devuelve (cuántos, hubo_sin_margen).

    La regla, literal: si una lista no tiene margen cargado, su precio NO SE TOCA. No se
    inventa un margen ni se hereda el de otra lista — un precio de venta inventado por una
    máquina es exactamente lo que nadie quiere en un mostrador.
    """
    recalculados = 0
    sin_margen = False

    for precio_fila, _lista in catalogo.listar_precios_de_articulo(session, org_id, articulo_id):
        if precio_fila.margen is None:
            sin_margen = True
            continue
        catalogo.upsert_precio(
            session,
            org_id,
            articulo_id=articulo_id,
            lista_id=precio_fila.lista_id,
            precio=catalogo.calcular_precio(costo, precio_fila.margen),
            margen=precio_fila.margen,
        )
        recalculados += 1

    return recalculados, sin_margen


def confirmar(
    session: Session,
    org_id: UUID,
    *,
    datos: ConfirmarRequest,
    usuario_id: UUID | None = None,
) -> ConfirmarResponse:
    """Escribe lo que el humano aprobó. UN REMITO = UNA TRANSACCIÓN: o entran todos los
    renglones o no entra ninguno. No existe el remito a medias.

    No abre sesión ni commitea — recibe la sesión del request y termina en flush(). El commit
    lo hace `get_tenant` después de que la respuesta se produjo (app/core/rls.py). Si algo
    explota, el rollback deja la base como estaba.

    El orden de los pasos NO es cosmético: `remitos_procesados` se inserta PRIMERO porque su
    unique index es el candado de concurrencia (dos confirmaciones simultáneas: una gana, la
    otra se lleva un IntegrityError → 409) y porque su id es lo que el kardex referencia.
    """
    deposito = inventario.obtener_deposito(session, org_id, datos.deposito_codigo)
    if deposito is None:
        # `registrar_movimiento` no valida que el depósito sea de esta org (confía en la FK
        # y en RLS). Este chequeo explícito es la primera barrera, y da un error entendible
        # en vez de un fallo de FK a mitad de la escritura.
        raise DatoInvalido(f"No existe el depósito {datos.deposito_codigo!r} en tu organización.")

    proveedor = None
    if datos.proveedor_codigo:
        proveedor = proveedores.obtener_o_crear_proveedor(
            session,
            org_id,
            codigo=datos.proveedor_codigo,
            razon_social=datos.proveedor_razon_social or datos.proveedor_codigo,
            cuit=datos.proveedor_cuit,
        )

    remito = RemitoProcesado(
        org_id=org_id,
        imagen_hash=datos.remito_hash,
        proveedor_id=proveedor.id if proveedor else None,
        numero_remito=datos.numero_remito,
        fecha_remito=datos.fecha,
        total_declarado=datos.total_declarado,
        renglones_count=len(datos.renglones),
        # El payload EXACTO que se aprobó. Auditoría barata: dentro de seis meses, la
        # pregunta "¿quién metió este costo?" se contesta con una fila.
        propuesta=datos.model_dump(mode="json"),
        creado_por=usuario_id,
    )
    session.add(remito)
    session.flush()  # ⇐ acá pega el unique si el remito ya se cargó: IntegrityError → 409

    creados: list[str] = []
    actualizados: list[str] = []
    sin_margen: list[str] = []
    tocados: list = []
    movimientos = 0
    recalculados = 0

    for renglon in datos.renglones:
        articulo = catalogo.obtener_articulo(session, org_id, renglon.codigo)

        if articulo is None:
            articulo = catalogo.crear_articulo(
                session,
                org_id,
                ArticuloCrear(
                    codigo=renglon.codigo,
                    detalle=renglon.detalle,
                    costo=renglon.costo_unitario,
                    alicuota_iva=renglon.alicuota_iva,
                    marca=renglon.marca,
                    rubro=renglon.rubro,
                ),
            )
            creados.append(renglon.codigo)
            tocados.append(articulo)
        else:
            catalogo.actualizar_articulo(
                session,
                org_id,
                articulo=articulo,
                datos=ArticuloActualizar(costo=renglon.costo_unitario),
            )
            actualizados.append(renglon.codigo)

            n, hubo_sin_margen = _recalcular_precios(
                session, org_id, articulo_id=articulo.id, costo=renglon.costo_unitario
            )
            recalculados += n
            if hubo_sin_margen:
                sin_margen.append(renglon.codigo)

        if proveedor is not None:
            proveedores.upsert_vinculo_articulo(
                session,
                org_id,
                articulo_id=articulo.id,
                proveedor_id=proveedor.id,
                codigo_proveedor=renglon.codigo_proveedor,
                costo=renglon.costo_unitario,
            )

        inventario.registrar_movimiento(
            session,
            org_id,
            articulo_id=articulo.id,
            deposito_id=deposito.id,
            cantidad=renglon.cantidad,
            motivo="compra",
            ref_tipo="remito",
            ref_id=remito.id,
            usuario_id=usuario_id,
        )
        movimientos += 1

    # Los artículos NUEVOS necesitan su vector ahora, en esta misma transacción: si no,
    # quedan invisibles a la búsqueda semántica hasta que corra un batch. Los editados no
    # se re-embeben acá porque solo les cambió el costo, que no entra en el texto indexado.
    catalogo.asegurar_embeddings(session, org_id, articulos=tocados)

    advertencias = []
    if sin_margen:
        advertencias.append(
            f"{len(sin_margen)} artículo(s) quedaron con el precio anterior porque no "
            "tienen margen cargado. Revisalos a mano."
        )
    if creados:
        advertencias.append(
            f"{len(creados)} artículo(s) se crearon SIN precio de venta. Poneles precio "
            "antes de venderlos."
        )

    return ConfirmarResponse(
        remito_id=remito.id,
        articulos_creados=creados,
        articulos_actualizados=actualizados,
        movimientos=movimientos,
        precios_recalculados=recalculados,
        renglones_sin_margen=sin_margen,
        advertencias=advertencias,
    )
