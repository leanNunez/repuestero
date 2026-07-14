from collections.abc import Iterable
from pathlib import Path

from app.importador.readers.base import (
    AplicacionRaw,
    ArticuloProveedorRaw,
    ArticuloRaw,
    ClienteRaw,
    PrecioRaw,
    ProveedorRaw,
    StockInicialRaw,
    VehiculoRaw,
)

_FASE_2 = (
    "El lector de Paradox es Fase 2. El hook está listo: implementá estos métodos "
    "y el loader lo consume sin cambiar una línea."
)


class ParadoxSourceReader:
    """HOOK PARA FASE 2 — lector de las tablas Paradox (`.DB`) del sistema legacy.

    Esto no es un TODO olvidado: es el arma de onboarding del producto. Los competidores
    importan de Excel; poder leer el Paradox directo elimina la objeción número uno del
    dueño de la repuestera ("pierdo mi historia de 20 años").

    El mapeo que va a implementar, ya relevado en docs/analisis-legacy.md §2:

        Articulos            -> ArticuloRaw          (Precio0..3 -> PrecioRaw x N listas)
        ArticulosStock       -> StockInicialRaw      (una fila por depósito)
        ArticulosProveedores -> ArticuloProveedorRaw
        Clientes             -> ClienteRaw           (¡sanear CUIT/teléfono/email!)
        Proveedores          -> ProveedorRaw
        Vehiculos            -> VehiculoRaw          (OJO: en el legacy están VACÍAS)

    Trampas ya conocidas del legacy, para no comerlas de nuevo:
      - Códigos de artículo Alpha(20) referenciados como Alpha(6): vienen TRUNCADOS (§4.4).
      - Conviven copias basura en la misma carpeta (`Articulos20250129`,
        `ClientesCtaCteMAL...`): hay que ignorarlas explícitamente (§4.5).
      - Los teléfonos y emails son campos libres sin validar: entran sucios (§5.C).
    """

    def __init__(self, carpeta_bases: Path) -> None:
        self.carpeta_bases = carpeta_bases

    def listas_precio(self) -> Iterable[tuple[str, str]]:
        raise NotImplementedError(_FASE_2)

    def depositos(self) -> Iterable[tuple[str, str]]:
        raise NotImplementedError(_FASE_2)

    def articulos(self) -> Iterable[ArticuloRaw]:
        raise NotImplementedError(_FASE_2)

    def precios(self) -> Iterable[PrecioRaw]:
        raise NotImplementedError(_FASE_2)

    def proveedores(self) -> Iterable[ProveedorRaw]:
        raise NotImplementedError(_FASE_2)

    def articulo_proveedores(self) -> Iterable[ArticuloProveedorRaw]:
        raise NotImplementedError(_FASE_2)

    def clientes(self) -> Iterable[ClienteRaw]:
        raise NotImplementedError(_FASE_2)

    def vehiculos(self) -> Iterable[VehiculoRaw]:
        raise NotImplementedError(_FASE_2)

    def aplicaciones(self) -> Iterable[AplicacionRaw]:
        raise NotImplementedError(_FASE_2)

    def stock_inicial(self) -> Iterable[StockInicialRaw]:
        raise NotImplementedError(_FASE_2)
