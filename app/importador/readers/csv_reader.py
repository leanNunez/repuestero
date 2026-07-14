import csv
from collections.abc import Iterable, Iterator
from decimal import Decimal
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


def _dec(valor: str | None) -> Decimal:
    """Los importes se leen como Decimal DESDE EL STRING. Nunca pasando por float.

    `Decimal(float("0.1"))` te devuelve 0.1000000000000000055511151231257827. Eso, sumado
    diez mil veces en una cuenta corriente, es plata que no cierra. Por eso `Decimal(str)`.
    """
    return Decimal((valor or "0").strip() or "0")


def _int_o_none(valor: str | None) -> int | None:
    valor = (valor or "").strip()
    return int(valor) if valor else None


def _txt(valor: str | None) -> str | None:
    valor = (valor or "").strip()
    return valor or None


def _bool(valor: str | None) -> bool:
    return (valor or "").strip().lower() in {"1", "true", "si", "sí", "x"}


class CsvSourceReader:
    """Adaptador CSV. Lee el slice de ejemplo de `seeds/demo/`.

    CSV y no JSON a propósito: es lo que va a escupir el export de Paradox en Fase 2, es
    legible sin herramientas, y diffea limpio en git.
    """

    def __init__(self, carpeta: Path) -> None:
        self.carpeta = carpeta

    def _filas(self, archivo: str) -> Iterator[dict[str, str]]:
        ruta = self.carpeta / archivo
        if not ruta.exists():
            return
        with ruta.open(encoding="utf-8", newline="") as fh:
            yield from csv.DictReader(fh)

    def listas_precio(self) -> Iterable[tuple[str, str]]:
        for f in self._filas("listas_precio.csv"):
            yield f["codigo"], f["nombre"]

    def depositos(self) -> Iterable[tuple[str, str]]:
        for f in self._filas("depositos.csv"):
            yield f["codigo"], f["nombre"]

    def articulos(self) -> Iterable[ArticuloRaw]:
        for f in self._filas("articulos.csv"):
            yield ArticuloRaw(
                codigo=f["codigo"].strip(),
                detalle=f["detalle"].strip(),
                costo=_dec(f.get("costo")),
                alicuota_iva=_dec(f.get("alicuota_iva")),
                punto_pedido=_dec(f.get("punto_pedido")),
                marca=_txt(f.get("marca")),
                rubro=_txt(f.get("rubro")),
                codigo_barra=_txt(f.get("codigo_barra")),
            )

    def precios(self) -> Iterable[PrecioRaw]:
        for f in self._filas("articulo_precios.csv"):
            margen = f.get("margen", "").strip()
            yield PrecioRaw(
                articulo_codigo=f["articulo_codigo"].strip(),
                lista_codigo=f["lista_codigo"].strip(),
                precio=_dec(f["precio"]),
                margen=_dec(margen) if margen else None,
            )

    def proveedores(self) -> Iterable[ProveedorRaw]:
        for f in self._filas("proveedores.csv"):
            yield ProveedorRaw(
                codigo=f["codigo"].strip(),
                razon_social=f["razon_social"].strip(),
                cuit=_txt(f.get("cuit")),
                telefono=_txt(f.get("telefono")),
                email=_txt(f.get("email")),
            )

    def articulo_proveedores(self) -> Iterable[ArticuloProveedorRaw]:
        for f in self._filas("articulo_proveedores.csv"):
            yield ArticuloProveedorRaw(
                articulo_codigo=f["articulo_codigo"].strip(),
                proveedor_codigo=f["proveedor_codigo"].strip(),
                codigo_proveedor=_txt(f.get("codigo_proveedor")),
                costo=_dec(f.get("costo")),
                es_preferido=_bool(f.get("es_preferido")),
            )

    def clientes(self) -> Iterable[ClienteRaw]:
        for f in self._filas("clientes.csv"):
            yield ClienteRaw(
                codigo=f["codigo"].strip(),
                denominacion=f["denominacion"].strip(),
                cuit=_txt(f.get("cuit")),
                cond_fiscal=f.get("cond_fiscal", "CONSUMIDOR_FINAL").strip(),
                limite_cta_cte=_dec(f.get("limite_cta_cte")),
                telefono=_txt(f.get("telefono")),
                email=_txt(f.get("email")),
                direccion=_txt(f.get("direccion")),
            )

    def vehiculos(self) -> Iterable[VehiculoRaw]:
        for f in self._filas("vehiculos.csv"):
            yield VehiculoRaw(
                marca=f["marca"].strip(),
                modelo=f["modelo"].strip(),
                anio_desde=_int_o_none(f.get("anio_desde")),
                anio_hasta=_int_o_none(f.get("anio_hasta")),
                motor=_txt(f.get("motor")),
                version=_txt(f.get("version")),
            )

    def aplicaciones(self) -> Iterable[AplicacionRaw]:
        for f in self._filas("articulo_aplicaciones.csv"):
            yield AplicacionRaw(
                articulo_codigo=f["articulo_codigo"].strip(),
                vehiculo_marca=f["vehiculo_marca"].strip(),
                vehiculo_modelo=f["vehiculo_modelo"].strip(),
                vehiculo_anio_desde=_int_o_none(f.get("vehiculo_anio_desde")),
                vehiculo_anio_hasta=_int_o_none(f.get("vehiculo_anio_hasta")),
                origen=f.get("origen", "manual").strip() or "manual",
                confirmado=_bool(f.get("confirmado")),
                nota=_txt(f.get("nota")),
            )

    def stock_inicial(self) -> Iterable[StockInicialRaw]:
        for f in self._filas("stock_inicial.csv"):
            yield StockInicialRaw(
                articulo_codigo=f["articulo_codigo"].strip(),
                deposito_codigo=f["deposito_codigo"].strip(),
                cantidad=_dec(f["cantidad"]),
            )
