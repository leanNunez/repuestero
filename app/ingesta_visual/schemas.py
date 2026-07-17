"""Los contratos de la ingesta visual.

Tres familias, y la separación es deliberada:

- `*Extraido`: lo que devuelve el LLM. Nunca toca la DB. Es una PROPUESTA.
- `*Propuesta`: lo que ve el humano — lo extraído + lo que ya sabe el sistema + los flags.
- `*Confirmar`: lo que el humano aprobó. Es lo único que puede escribir.

El schema de confirmación NO confía en que el payload venga de `/extraer`. El servidor no
recuerda la propuesta entre las dos llamadas (ese es el precio explícito de hacer HITL sin
interrupt), así que `/confirmar` se valida como input hostil, igual que cualquier POST.
"""

from datetime import date, datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from app.core.config import get_settings
from app.ingesta_visual.imagen import MIMES_ACEPTADOS, max_chars_base64

_s = get_settings()

#: Slugs de atención humana. Son strings y no un Enum porque viajan al front como badges y
#: la lista crece con la experiencia de uso, no con el modelo de dominio.
Flag = Literal[
    "sin_codigo",
    "sin_margen",
    "sin_listas",
    "baja_confianza",
    "salto_de_costo",
    "costo_cero",
    "duplicado",
    "texto_sospechoso",
    "alta_sin_precio",
]


# --------------------------------------------------------------------------- entrada

class ExtraerRequest(BaseModel):
    """El techo de tamaño vive ACÁ, en el boundary, sobre el string base64.

    Es la única defensa que sirve: rechazar por tamaño DESPUÉS de decodificar significa
    haber decodificado el ataque. Pydantic corta antes de que el string llegue a memoria
    como bytes.
    """

    imagen_base64: str = Field(
        min_length=100,
        max_length=max_chars_base64(_s.ingesta_max_imagen_mb),
    )
    mime: Literal[MIMES_ACEPTADOS] = "image/jpeg"  # type: ignore[valid-type]


# --------------------------------------------------------------------------- lo que devuelve el LLM

class RenglonExtraido(BaseModel):
    """Un renglón tal como lo leyó el modelo. Todavía no se comparó con nada."""

    codigo: str | None = Field(default=None, max_length=40)
    descripcion: str = Field(max_length=200)
    cantidad: Decimal
    costo_unitario: Decimal
    #: Lo que el modelo dice sobre su propia lectura. HINT de UI, jamás un gate:
    #: la auto-confianza de un LLM está mal calibrada. El gate es el humano.
    confianza: float = Field(default=0.5, ge=0, le=1)


class RemitoExtraido(BaseModel):
    proveedor_nombre: str | None = Field(default=None, max_length=120)
    proveedor_cuit: str | None = Field(default=None, max_length=13)
    numero_remito: str | None = Field(default=None, max_length=40)
    fecha: date | None = None
    #: El total impreso en el papel. No es un dato contable: es un CHECKSUM gratis contra
    #: errores de OCR (ver la regla `no_cuadra` en flags.py).
    total_declarado: Decimal | None = None
    renglones: list[RenglonExtraido] = Field(
        default_factory=list, max_length=_s.ingesta_max_renglones
    )


# --------------------------------------------------------------------------- la propuesta

class PrecioPreview(BaseModel):
    """Qué pasaría con un precio si se confirma. `precio_nuevo is None` ⇔ no hay margen."""

    lista_codigo: str
    lista_nombre: str
    precio_actual: Decimal
    margen: Decimal | None
    #: None cuando `margen` es None: sin margen cargado NO se inventa un precio.
    precio_nuevo: Decimal | None


class RenglonPropuesta(BaseModel):
    codigo: str | None
    descripcion: str
    cantidad: Decimal
    costo_unitario: Decimal
    confianza: float

    accion: Literal["alta", "actualizacion"]
    articulo_id: int | None = None
    detalle_actual: str | None = None
    costo_actual: Decimal | None = None
    precios: list[PrecioPreview] = Field(default_factory=list)
    atencion: list[Flag] = Field(default_factory=list)
    #: Sugerencia del server: en qué renglones el front debería arrancar con el check
    #: DESACTIVADO. El default seguro es NO escribir.
    incluir_sugerido: bool = True


class PropuestaResponse(BaseModel):
    remito_hash: str
    #: True ⇒ este remito ya se cargó. No se llamó al LLM y no hay nada que confirmar.
    ya_procesado: bool = False
    procesado_en: datetime | None = None

    proveedor_nombre: str | None = None
    proveedor_cuit: str | None = None
    numero_remito: str | None = None
    fecha: date | None = None
    total_declarado: Decimal | None = None
    total_calculado: Decimal = Decimal("0")
    renglones: list[RenglonPropuesta] = Field(default_factory=list)
    advertencias: list[str] = Field(default_factory=list)


# --------------------------------------------------------------------------- la confirmación

class RenglonConfirmar(BaseModel):
    """Un renglón que el humano revisó y aprobó.

    `codigo` es obligatorio acá aunque sea opcional en la extracción: si la IA no lo leyó,
    lo completa la persona. No se puede dar de alta un artículo sin código — es su identidad
    dentro de la organización.
    """

    model_config = ConfigDict(str_strip_whitespace=True)

    codigo: str = Field(min_length=1, max_length=40)
    detalle: str = Field(min_length=1, max_length=200)
    cantidad: Decimal = Field(gt=0)
    costo_unitario: Decimal = Field(ge=0)
    marca: str | None = Field(default=None, max_length=60)
    rubro: str | None = Field(default=None, max_length=60)
    alicuota_iva: Decimal = Decimal("21.00")
    codigo_proveedor: str | None = Field(default=None, max_length=40)


class ConfirmarRequest(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    #: Ata la escritura a una imagen concreta y es el candado de idempotencia.
    remito_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    numero_remito: str | None = Field(default=None, max_length=40)
    fecha: date | None = None
    total_declarado: Decimal | None = None

    proveedor_codigo: str | None = Field(default=None, max_length=20)
    proveedor_razon_social: str | None = Field(default=None, max_length=120)
    proveedor_cuit: str | None = Field(default=None, max_length=13)

    #: A qué depósito entra la mercadería. Sin default: que la plata y el stock vayan a
    #: parar a un lugar por omisión es exactamente como se pierde el control del inventario.
    deposito_codigo: str = Field(min_length=1, max_length=20)

    renglones: list[RenglonConfirmar] = Field(
        min_length=1, max_length=_s.ingesta_max_renglones
    )


class ConfirmarResponse(BaseModel):
    remito_id: int
    articulos_creados: list[str] = Field(default_factory=list)
    articulos_actualizados: list[str] = Field(default_factory=list)
    movimientos: int = 0
    precios_recalculados: int = 0
    #: Los que quedaron con el precio viejo porque no había margen con qué recalcular.
    #: No es un error: es la regla. Pero el humano tiene que enterarse.
    renglones_sin_margen: list[str] = Field(default_factory=list)
    advertencias: list[str] = Field(default_factory=list)
