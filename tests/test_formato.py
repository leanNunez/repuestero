"""Formato de importes para los textos que lee una persona (`app/core/formato.py`)."""

from decimal import Decimal

import pytest

from app.core.formato import pesos


@pytest.mark.parametrize(
    ("monto", "esperado"),
    [
        (Decimal("9506.97"), "9.506,97"),
        (Decimal("1000"), "1.000,00"),
        (Decimal("0"), "0,00"),
        (Decimal("999.5"), "999,50"),
        (Decimal("1234567.89"), "1.234.567,89"),  # dos separadores de miles
        (Decimal("-1500.25"), "-1.500,25"),
    ],
)
def test_formato_es_AR(monto, esperado):
    assert pesos(monto) == esperado


def test_no_deja_rastro_del_formato_de_EEUU():
    """El paso por `_` es lo que impide que la coma decimal recién puesta se vuelva punto."""
    salida = pesos(Decimal("1234.56"))

    assert salida == "1.234,56"
    assert "_" not in salida
