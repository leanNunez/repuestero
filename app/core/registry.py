"""Importa todos los modelos para que `Base.metadata` esté completo.

Alembic autogenera comparando `Base.metadata` contra la base real. Un modelo que nadie
importó simplemente NO EXISTE para el autogenerate, y la migración sale incompleta sin
avisar. Este módulo es el único lugar que tiene que acordarse de todos.

Lo importa `alembic/env.py`. Cuando agregues un feature, sumá su import acá.
"""

from app.catalogo import models as catalogo_models
from app.clientes import models as clientes_models
from app.compatibilidad import models as compatibilidad_models
from app.core import models as core_models
from app.core.base import Base
from app.inventario import models as inventario_models
from app.proveedores import models as proveedores_models

#: Tablas del dominio que llevan org_id y por lo tanto necesitan políticas de RLS.
#: `organizaciones` no está: es la raíz del tenant, no tiene org_id propio.
#: `miembros` tampoco: su política filtra por usuario, no por org (ver core/models.py).
TABLAS_TENANT: tuple[str, ...] = (
    "articulos",
    "listas_precio",
    "articulo_precios",
    "depositos",
    "stock_movimientos",
    "clientes",
    "proveedores",
    "articulo_proveedores",
    "vehiculos",
    "articulo_aplicaciones",
)

__all__ = [
    "Base",
    "TABLAS_TENANT",
    "catalogo_models",
    "clientes_models",
    "compatibilidad_models",
    "core_models",
    "inventario_models",
    "proveedores_models",
]
