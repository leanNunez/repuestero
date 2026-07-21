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


class ListaPrecioCrear(BaseModel):
    codigo: str = Field(max_length=30)
    nombre: str = Field(max_length=80)


class PrecioCrear(BaseModel):
    articulo_codigo: str
    lista_codigo: str
    precio: Decimal
    margen: Decimal | None = None
