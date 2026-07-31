from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field


class ArticuloCrear(BaseModel):
    codigo: str = Field(max_length=40)
    detalle: str = Field(max_length=200)
    costo: Decimal = Decimal("0")
    costo_dolar: Decimal | None = None
    alicuota_iva: Decimal = Decimal("21.00")
    punto_pedido: Decimal = Decimal("0")
    codigo_barra: str | None = None
    marca: str | None = None
    rubro: str | None = None


class ArticuloAltaRequest(ArticuloCrear):
    """Lo que manda el alta de la app: un artículo + la intención de fijarle un precio.

    El precio NO es un campo del artículo (vive en `articulo_precios`, por lista), pero se
    acepta acá para que cargar un producto vendible sea una sola operación atómica en vez de
    dos llamadas que pueden quedar a medias.

    `precio` sin `lista_id` es 422, no un default silencioso: no hay lista por defecto a nivel
    sistema, y elegir una en silencio sería inventar el precio de venta de un artículo.
    """

    precio: Decimal | None = Field(default=None, gt=0)
    lista_id: int | None = None


class ArticuloActualizar(BaseModel):
    """Update parcial: solo se pisan los campos que vengan seteados.

    El `codigo` NO está: es la identidad del artículo dentro de la org. Cambiarlo no es
    editar, es otra cosa (y rompería las referencias del proveedor). `activo` tampoco:
    dar de baja un artículo es una decisión, no un efecto colateral de cargar un remito.
    """

    detalle: str | None = Field(default=None, max_length=200)
    costo: Decimal | None = None
    costo_dolar: Decimal | None = None
    alicuota_iva: Decimal | None = None
    punto_pedido: Decimal | None = None
    codigo_barra: str | None = None
    marca: str | None = None
    rubro: str | None = None


class ArticuloLeer(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    codigo: str
    detalle: str
    costo: Decimal
    alicuota_iva: Decimal
    punto_pedido: Decimal
    marca: str | None
    rubro: str | None
    activo: bool


class ResultadoBusqueda(ArticuloLeer):
    """Un artículo con su puntaje de relevancia en la búsqueda híbrida (mayor = más relevante)."""

    score: float


class ArticuloPagina(BaseModel):
    """Una página del listado + el total del resultado filtrado (para paginar en el front)."""

    items: list[ArticuloLeer]
    total: int


class ArticuloAltaResponse(BaseModel):
    """El artículo creado + los avisos no bloqueantes del alta.

    Anidado y no plano: `advertencias` NO se agrega a `ArticuloLeer` porque ese schema alimenta
    tres endpoints de lectura y es la base de `ResultadoBusqueda`. El campo se colaría como
    `"advertencias": []` en cada fila de cada página del listado y de cada búsqueda — ruido en
    el cable, y mentira en el contrato: una fila de listado no tiene advertencias.
    """

    articulo: ArticuloLeer
    advertencias: list[str] = Field(default_factory=list)


class ListaPrecioCrear(BaseModel):
    codigo: str = Field(max_length=30)
    nombre: str = Field(max_length=80)


class PrecioCrear(BaseModel):
    articulo_codigo: str
    lista_codigo: str
    precio: Decimal
    margen: Decimal | None = None
