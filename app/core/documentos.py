"""Con qué documento se identifica al receptor de un comprobante ante ARCA.

Vive en `core` y no en `clientes` por lo mismo que `core/cuit.py`: el día que existan las notas
de crédito de compra, `proveedores` va a necesitar exactamente esto, y que un módulo importe del
otro sería atarlos por algo que no es de ninguno de los dos.

Recibe VALORES, no un `Cliente`. A propósito: así es una función pura, testeable sin base, y no
queda acoplada a que las columnas se llamen como se llaman hoy.
"""

from app.core.arca import DOC_TIPO_CUIT, DOC_TIPO_SIN_IDENTIFICAR

#: Lo que se declara cuando el que compra no se identificó. Es el par que ARCA espera para el
#: mostrador anónimo: tipo 99, número 0.
SIN_IDENTIFICAR: tuple[int, str] = (DOC_TIPO_SIN_IDENTIFICAR, "0")


def documento_de(
    *, doc_tipo: int | None = None, doc_nro: str | None = None, cuit: str | None = None
) -> tuple[int, str]:
    """Devuelve el par `(DocTipo, DocNro)` a declarar, por orden de precedencia.

    1. **El documento explícito**, si lo cargaron. Es el único que puede expresar un DNI, y por
       eso gana: un consumidor final con DNI cargado tiene que viajar como DNI, no como anónimo.
    2. **El CUIT**, que ya viene validado por módulo 11 desde el alta (`core/cuit.py`). Se manda
       sin guiones porque ARCA quiere los once dígitos pelados.
    3. **Sin identificar**, que es la verdad cuando no hay ningún dato.

    Ojo con el orden: nunca cae a `SIN_IDENTIFICAR` teniendo un dato mejor. Declarar anónimo a
    alguien que dio su CUIT es perder el comprobante para el que lo recibe.
    """
    if doc_tipo is not None and doc_nro:
        return doc_tipo, doc_nro

    if cuit:
        return DOC_TIPO_CUIT, cuit.replace("-", "")

    return SIN_IDENTIFICAR
