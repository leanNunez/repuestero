"""Qué letra de comprobante corresponde a una venta: A, B o C.

Está separado de `core/arca.py` a propósito, y la distinción no es cosmética: `arca.py` son
TABLAS DE CÓDIGO que publica ARCA, esto es **ley argentina** (RG 1415 y concordantes). Si mañana
ARCA renumera sus códigos, se toca `arca.py`; si cambia el régimen impositivo, se toca esto.

Vive en `core` y no en `app/afip/` porque `ventas` lo necesita ANTES de que exista ninguna
llamada a ARCA: la letra decide el código de comprobante, el código decide el espacio de
numeración, y el número se asigna mucho antes de hablar con nadie. Si esto viviera en `afip`,
`ventas` tendría que importar el módulo de la integración para poder numerar. Es el mismo
criterio con el que el `Numerador` salió de `ventas` hacia `core/numeracion.py`.
"""

from app.core.cond_fiscal import CONDICIONES_FISCALES, CONDICIONES_FISCALES_EMISOR

#: Todas las letras que el sistema sabe MANEJAR, que no es lo mismo que las que sabe DERIVAR.
#:
#: La **M** (RG 1575) está acá porque hay que poder procesarla —tiene sus códigos en `arca.py` y
#: declara IVA como la A—, pero `letra_de` **nunca la devuelve**: se emite M en lugar de A cuando
#: ARCA no da por probada la solvencia de un responsable inscripto recién inscripto, y eso lo
#: comunica ARCA, no se deriva de ningún dato nuestro. La **E** de exportación queda fuera.
#:
#: La distinción importa: una validación escrita como `if letra in LETRAS` tiene que aceptar una M
#: legítima. Lo que `letra_de` produce es el subconjunto `LETRAS_DERIVABLES`.
LETRAS: frozenset[str] = frozenset({"A", "B", "C", "M"})

#: Las que `letra_de` puede decidir sola, a partir de las condiciones fiscales.
LETRAS_DERIVABLES: frozenset[str] = frozenset({"A", "B", "C"})

#: Quiénes reciben factura A de un responsable inscripto: los que están inscriptos en el régimen.
#:
#: ⚠️ **MONOTRIBUTO está acá, y es el error que más se comete.** Un monotributista no puede
#: computar el crédito fiscal, y por eso mucha gente asume que le corresponde B. Le corresponde
#: **A**. El daño de equivocarse es silencioso: ARCA no rechaza una B (es un comprobante
#: perfectamente válido), así que el error no aparece al emitir sino meses después, en una
#: inspección, multiplicado por todos los comprobantes mal emitidos.
_RECIBEN_A: frozenset[str] = frozenset({"RESPONSABLE_INSCRIPTO", "MONOTRIBUTO"})

#: Quiénes pueden EMITIR comprobantes: `CONSUMIDOR_FINAL` no está porque un consumidor final no
#: emite, recibe.
#:
#: Es un alias de `CONDICIONES_FISCALES_EMISOR`, NO una segunda copia. Tenerlo dos veces se veía
#: inofensivo y no lo es: al sumar un emisor a una sola de las dos listas, `letra_de` lo aceptaría
#: y devolvería "C" mientras el test que barre la matriz sigue verde, porque arma sus expectativas
#: desde la OTRA lista.
#:
#: ⚠️ Hoy esta es la ÚNICA reja. `organizaciones` todavía no tiene columna `cond_fiscal` (llega con
#: la migración 0014, que no existe aún), así que nada impide guardar una organización con una
#: condición fiscal que no puede emitir: el error recién aparece acá, al facturar.
EMISORES_VALIDOS = CONDICIONES_FISCALES_EMISOR


class EmisorInvalido(ValueError):
    """La organización no puede emitir comprobantes con esa condición fiscal."""


class ReceptorInvalido(ValueError):
    """La condición fiscal del cliente no es una del vocabulario."""


def letra_de(emisor: str, receptor: str) -> str:
    """Letra del comprobante según la condición fiscal del emisor y la del receptor.

    Tres reglas generan la matriz completa:

    1. **Solo un responsable inscripto discrimina IVA**, y por eso es el único que emite A o B.
       La A va a quien está inscripto en el régimen (responsable inscripto y monotributista); la
       B a quien no lo está (consumidor final, exento).
    2. **Monotributista y exento emiten siempre C**, a cualquier receptor, sin excepción. Un
       monotributista no emite A ni B nunca.
    3. **Un consumidor final no emite.**

    ==========================  =====  ===========  ======  =============
    emisor \\ receptor          R.I.   MONOTRIBUTO  EXENTO  CONS. FINAL
    ==========================  =====  ===========  ======  =============
    RESPONSABLE_INSCRIPTO       A      A            B       B
    MONOTRIBUTO                 C      C            C       C
    EXENTO                      C      C            C       C
    CONSUMIDOR_FINAL            ✗      ✗            ✗       ✗
    ==========================  =====  ===========  ======  =============
    """
    if receptor not in CONDICIONES_FISCALES:
        raise ReceptorInvalido(f"'{receptor}' no es una condición fiscal conocida.")

    if emisor not in EMISORES_VALIDOS:
        raise EmisorInvalido(
            f"Una organización '{emisor}' no puede emitir comprobantes. "
            f"Las que sí pueden: {sorted(EMISORES_VALIDOS)}."
        )

    if emisor != "RESPONSABLE_INSCRIPTO":
        return "C"

    return "A" if receptor in _RECIBEN_A else "B"


def declara_iva(letra: str) -> bool:
    """Si el comprobante viaja a ARCA con IVA declarado (`ImpIVA` y array de alícuotas).

    OJO con no confundirlo con "discriminar" el IVA, que es un concepto de IMPRESIÓN: la A lo
    muestra desglosado y la B lo lleva incluido en el precio. Pero ante ARCA **las dos se
    declaran igual**, con su neto, su IVA y sus alícuotas. La única que no es la C.

    Una **factura C** exige `ImpIVA = 0`, `ImpNeto = ImpTotal` y el array de alícuotas **vacío**.
    Mandar alícuotas en una C es rechazo directo, y es el error que se cuela cuando el mismo
    código arma las tres letras sin preguntar cuál es.

    Esta función responde por lo que viaja en el request. El día que exista la impresión del
    comprobante, el desglose visual será otra función y otra regla.
    """
    if letra not in LETRAS:
        raise ValueError(f"'{letra}' no es una letra de comprobante conocida.")
    return letra != "C"
