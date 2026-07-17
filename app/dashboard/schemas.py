from decimal import Decimal

from pydantic import BaseModel


class ResumenKPIs(BaseModel):
    total_articulos: int
    bajo_punto_pedido: int
    margen_bajo: int
    valor_stock: Decimal


class ReposicionItem(BaseModel):
    codigo: str
    detalle: str
    marca: str | None
    stock: Decimal
    punto_pedido: Decimal
    faltante: Decimal


class MargenItem(BaseModel):
    codigo: str
    detalle: str
    marca: str | None
    costo: Decimal
    precio: Decimal
    #: Margen real = (precio - costo) / precio * 100.
    margen: Decimal
    #: True si el margen quedó por debajo del umbral objetivo (lo que vigila el guardián).
    bajo: bool
