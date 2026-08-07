"""Con qué documento se identifica al receptor de un comprobante ante ARCA.

Vive en `core` y no en `clientes` por lo mismo que `core/cuit.py`: el día que existan las notas
de crédito de compra, `proveedores` va a necesitar exactamente esto, y que un módulo importe del
otro sería atarlos por algo que no es de ninguno de los dos.

Recibe VALORES, no un `Cliente`. A propósito: así es una función pura, testeable sin base, y no
queda acoplada a que las columnas se llamen como se llaman hoy.
"""

import re

from app.core.arca import DOC_TIPO_CUIT, DOC_TIPO_SIN_IDENTIFICAR, DOC_TIPOS

#: Lo que se declara cuando el que compra no se identificó. Es el par que ARCA espera para el
#: mostrador anónimo: tipo 99, número 0.
SIN_IDENTIFICAR: tuple[int, str] = (DOC_TIPO_SIN_IDENTIFICAR, "0")

_NO_DIGITOS = re.compile(r"\D")


class DocumentoInvalido(ValueError):
    """El documento cargado no se puede declarar ante ARCA."""


def _solo_digitos(valor: str) -> str:
    """ARCA quiere el número pelado: sin guiones, puntos ni espacios.

    Se aplica a TODOS los documentos, no solo al CUIT. Un DNI cargado como "30.111.222" con los
    puntos adentro es un rechazo, y el mostrador los escribe así todo el tiempo.
    """
    return _NO_DIGITOS.sub("", valor)


def documento_de(
    *, doc_tipo: int | None = None, doc_nro: str | None = None, cuit: str | None = None
) -> tuple[int, str]:
    """Devuelve el par `(DocTipo, DocNro)` a declarar, por orden de precedencia.

    1. **El documento explícito**, si está completo. Es el único que puede expresar un DNI, y por
       eso gana: un consumidor final con DNI cargado tiene que viajar como DNI, no como anónimo.
    2. **El CUIT**, que ya viene validado por módulo 11 desde el alta (`core/cuit.py`).
    3. **Sin identificar**, que es la verdad cuando no hay ningún dato.

    Nunca cae a `SIN_IDENTIFICAR` teniendo un dato mejor: declarar anónimo a alguien que dio su
    CUIT es arruinarle el comprobante al que lo recibe.

    "Completo" quiere decir tipo Y número: un número sin tipo no se puede declarar (no sabemos si
    esos ocho dígitos son un DNI o un pasaporte), así que se ignora y se baja al escalón siguiente.
    """
    if doc_tipo is not None:
        if doc_tipo not in DOC_TIPOS:
            raise DocumentoInvalido(f"{doc_tipo} no es un tipo de documento que ARCA acepte.")

        # El 99 es "sin identificar" y exige número 0. Cualquier otro valor es rechazo, y sale
        # gratis normalizarlo acá en vez de descubrirlo cuando el cliente ya se fue.
        if doc_tipo == DOC_TIPO_SIN_IDENTIFICAR:
            return SIN_IDENTIFICAR

        numero = _solo_digitos(doc_nro or "")
        if numero:
            return doc_tipo, numero

    if cuit:
        return DOC_TIPO_CUIT, _solo_digitos(cuit)

    return SIN_IDENTIFICAR
