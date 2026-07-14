from collections.abc import Iterable
from dataclasses import dataclass
from decimal import Decimal
from typing import Protocol


@dataclass(frozen=True, slots=True)
class ArticuloRaw:
    codigo: str
    detalle: str
    costo: Decimal
    alicuota_iva: Decimal
    punto_pedido: Decimal
    marca: str | None = None
    rubro: str | None = None
    codigo_barra: str | None = None


@dataclass(frozen=True, slots=True)
class PrecioRaw:
    articulo_codigo: str
    lista_codigo: str
    precio: Decimal
    margen: Decimal | None = None


@dataclass(frozen=True, slots=True)
class ClienteRaw:
    codigo: str
    denominacion: str
    cuit: str | None
    cond_fiscal: str
    limite_cta_cte: Decimal
    telefono: str | None = None
    email: str | None = None
    direccion: str | None = None


@dataclass(frozen=True, slots=True)
class ProveedorRaw:
    codigo: str
    razon_social: str
    cuit: str | None = None
    telefono: str | None = None
    email: str | None = None


@dataclass(frozen=True, slots=True)
class ArticuloProveedorRaw:
    articulo_codigo: str
    proveedor_codigo: str
    codigo_proveedor: str | None
    costo: Decimal
    es_preferido: bool = False


@dataclass(frozen=True, slots=True)
class VehiculoRaw:
    marca: str
    modelo: str
    anio_desde: int | None = None
    anio_hasta: int | None = None
    motor: str | None = None
    version: str | None = None


@dataclass(frozen=True, slots=True)
class AplicacionRaw:
    articulo_codigo: str
    vehiculo_marca: str
    vehiculo_modelo: str
    vehiculo_anio_desde: int | None
    vehiculo_anio_hasta: int | None
    origen: str = "manual"
    confirmado: bool = False
    nota: str | None = None


@dataclass(frozen=True, slots=True)
class StockInicialRaw:
    articulo_codigo: str
    deposito_codigo: str
    cantidad: Decimal


class SourceReader(Protocol):
    """El PUERTO. El loader habla contra esto y no le importa de dónde salen los datos.

    Hoy hay un adaptador CSV (Fase 0). En Fase 2 entra el de Paradox leyendo los `.DB` del
    sistema viejo, y el loader NO se toca ni una línea. Esa es toda la gracia de invertir la
    dependencia: el importador de Paradox — que es el arma de onboarding del producto — se
    enchufa acá sin refactorizar nada.
    """

    def listas_precio(self) -> Iterable[tuple[str, str]]: ...
    def depositos(self) -> Iterable[tuple[str, str]]: ...
    def articulos(self) -> Iterable[ArticuloRaw]: ...
    def precios(self) -> Iterable[PrecioRaw]: ...
    def proveedores(self) -> Iterable[ProveedorRaw]: ...
    def articulo_proveedores(self) -> Iterable[ArticuloProveedorRaw]: ...
    def clientes(self) -> Iterable[ClienteRaw]: ...
    def vehiculos(self) -> Iterable[VehiculoRaw]: ...
    def aplicaciones(self) -> Iterable[AplicacionRaw]: ...
    def stock_inicial(self) -> Iterable[StockInicialRaw]: ...
