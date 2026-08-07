"""Tablas de código de ARCA (ex AFIP), tal como las pide WSFEv1.

Vive en `core` por la misma razón que `core/formas_pago.py` y `core/cond_fiscal.py`: son
CONSTANTES DE VOCABULARIO, no comportamiento. Con un agregado propio: **son un vocabulario
AJENO**. No los elegimos nosotros — los publica ARCA en sus "tablas de parámetros", y el día
que cambien, cambian acá y en ningún otro lado.

Las cuatro tablas viven en UN archivo a propósito. Son un único sistema de códigos externo que
se versiona junto: cuando ARCA publica una revisión del manual, se tocan todas en el mismo
commit. Partirlas en cuatro módulos crearía cuatro archivos que nunca se tocan por separado.

Lo que NO vive acá es la regla de qué letra corresponde a cada venta: eso es ley argentina, no
tabla de ARCA, y vive en `core/letra.py`. La diferencia importa porque `ventas` necesita la
letra ANTES de que exista ninguna llamada a ARCA (la letra decide el espacio de numeración), y
por lo tanto no puede depender de este módulo ni de `app/afip/`.

⚠️ Por ahora estas tablas viven SOLO en Python: ninguna migración las usa todavía (la última es
la 0013). Cuando lleguen las 0014-0017, cada una va a congelar su propia copia en el CHECK que
cree —regla de 0008_compras.py, las migraciones nunca importan de acá— y el candado contra la
deriva va a ser un test que inserte cada valor y verifique que la base lo acepte. Ese test **no
existe todavía**; hasta que exista, nada garantiza que la base y este archivo digan lo mismo.
"""

from decimal import Decimal

#: Códigos de comprobante (`CbteTipo` de WSFEv1), indexados por (clase, letra).
#:
#: La clase es nuestro vocabulario interno ('FAC', 'ND', 'NC') y la letra sale de `core/letra.py`.
#: Están los tres juegos completos aunque el slice 1 solo emita facturas: agregar un código
#: después es gratis, pero olvidarse de uno el día que se emita la primera nota de crédito es
#: descubrirlo en el mostrador.
CODIGOS_COMPROBANTE: dict[tuple[str, str], int] = {
    ("FAC", "A"): 1,
    ("ND", "A"): 2,
    ("NC", "A"): 3,
    ("FAC", "B"): 6,
    ("ND", "B"): 7,
    ("NC", "B"): 8,
    ("FAC", "C"): 11,
    ("ND", "C"): 12,
    ("NC", "C"): 13,
    ("FAC", "M"): 51,
    ("ND", "M"): 52,
    ("NC", "M"): 53,
}

#: Los mismos códigos como conjunto, para el CHECK de `comprobantes.cbte_tipo`.
CODIGOS_VALIDOS: frozenset[int] = frozenset(CODIGOS_COMPROBANTE.values())


class ComprobanteNoFiscal(ValueError):
    """La combinación (clase, letra) no tiene código electrónico en ARCA."""


def codigo_comprobante(clase: str, letra: str) -> int:
    """Devuelve el `CbteTipo` de ARCA para una clase y letra.

    Levanta en vez de devolver `None` a propósito: un comprobante sin código no se puede
    autorizar, y descubrirlo con un `TypeError` tres capas más abajo es peor que acá.
    """
    codigo = CODIGOS_COMPROBANTE.get((clase, letra))
    if codigo is None:
        raise ComprobanteNoFiscal(f"No hay comprobante electrónico para ({clase}, {letra}).")
    return codigo


def clave_numeracion(cbte_tipo: int) -> str:
    """Clave del `Numerador` para un tipo de comprobante electrónico.

    ARCA exige un talonario INDEPENDIENTE por (punto de venta, tipo de comprobante): un
    responsable inscripto que emite Factura A y Factura B desde el mismo punto de venta tiene
    dos numeraciones, y **las dos arrancan en 1**. Por eso la clave cuelga del `cbte_tipo` y no
    de nuestro `'FAC'` interno, que mezclaría las dos en un solo contador y haría que el segundo
    comprobante enviado se lleve un rechazo por número fuera de secuencia.

    El prefijo `FE` mantiene el espacio separado de las claves no fiscales ('FAC', 'NC', 'REC',
    'OP') y entra holgado en el `String(10)` de `numeradores.tipo`.

    ⚠️ **Separar los talonarios es necesario pero NO suficiente.** Quedan dos agujeros que esta
    función sola no tapa, y que hay que resolver antes de la primera emisión real:

    1. **El contador arranca en 0.** `asignar_numero` crea la fila con `ultimo=0`, así que el
       primer comprobante de cada `FE0xx` sale con número 1. Para un CUIT que YA venía facturando
       (talonario autorizado en N), eso es exactamente el rechazo por número fuera de secuencia
       que esto viene a evitar. Hay que sembrar el numerador desde `FECompUltimoAutorizado`.
    2. **El unique de `comprobantes` todavía es `(org_id, tipo, pto_venta, numero)`** con
       `tipo='FAC'`. Si se saca el número del numerador `FE001` pero se deja `tipo='FAC'`, el
       contador nuevo arranca en 1 y choca contra los FAC 1..N ya emitidos → `IntegrityError` en
       la primera factura electrónica de toda org con historia. Por eso la migración 0016 parte
       ese unique en dos índices parciales según `cbte_tipo`.
    """
    return f"FE{cbte_tipo:03d}"


#: Ids de alícuota de IVA (array `Iva` de WSFEv1), por porcentaje.
#:
#: Los ids 1 ('No gravado') y 2 ('Exento') NO están, y no es un olvido: esos conceptos no viajan
#: en el array `Iva` sino en los campos `ImpTotConc` e `ImpOpEx` de la cabecera. Meterlos acá
#: invitaría a mandarlos donde ARCA los rechaza.
ALICUOTAS_ARCA: dict[Decimal, int] = {
    Decimal("0"): 3,
    Decimal("10.50"): 4,
    Decimal("21.00"): 5,
    Decimal("27.00"): 6,
    Decimal("5.00"): 8,
    Decimal("2.50"): 9,
}

#: Las seis alícuotas legales, para el CHECK de `alicuota_iva`. Es lo que convierte la regla
#: "IVA explícito por renglón" en "IVA FISCALMENTE VÁLIDO por renglón": hoy la columna acepta
#: cualquier porcentaje, y un 15% inventado no aparece hasta que ARCA rechaza el comprobante.
ALICUOTAS_LEGALES: frozenset[Decimal] = frozenset(ALICUOTAS_ARCA)


class AlicuotaNoFiscal(ValueError):
    """El porcentaje de IVA no es uno de los seis que ARCA acepta."""


def id_alicuota(porcentaje: Decimal) -> int:
    """Devuelve el Id de alícuota de ARCA para un porcentaje de IVA."""
    id_arca = ALICUOTAS_ARCA.get(porcentaje)
    if id_arca is None:
        raise AlicuotaNoFiscal(
            f"{porcentaje}% no es una alícuota de IVA que ARCA acepte "
            f"(las válidas son {sorted(ALICUOTAS_ARCA)})."
        )
    return id_arca


#: Tipos de documento del receptor (`DocTipo` de WSFEv1).
DOC_TIPOS: frozenset[int] = frozenset({80, 86, 87, 89, 90, 91, 92, 93, 94, 95, 96, 99})

#: Los tres que el mostrador usa de verdad. El resto entra en el CHECK para no tener que
#: migrar el día que alguien facture a un extranjero con pasaporte.
DOC_TIPO_CUIT = 80
DOC_TIPO_DNI = 96
DOC_TIPO_SIN_IDENTIFICAR = 99

#: `CondicionIVAReceptorId` (RG 4291, manuales 4.4/4.5) — **OBLIGATORIO** en cada comprobante.
#:
#: Mapea el vocabulario que la migración 0013 ya había cerrado. Que las cuatro condiciones de
#: `core/cond_fiscal.py` entren tal cual, sin ampliar ni renombrar nada, es exactamente lo que
#: aquel docstring buscaba con "se cierra ahora, antes de que exista AFIP, y no después".
COND_IVA_RECEPTOR: dict[str, int] = {
    "RESPONSABLE_INSCRIPTO": 1,
    "EXENTO": 4,
    "CONSUMIDOR_FINAL": 5,
    "MONOTRIBUTO": 6,
}

#: Los ids que ARCA acepta como receptor de cada letra.
#:
#: ⚠️ Esta matriz está construida a partir del manual, no consultada al servicio. Cuando aterrice
#: el backend WSFEv1 real hay que validarla contra `FEParamGetCondicionIvaReceptor`, que es la
#: fuente autoritativa. Para las cuatro condiciones que usamos es consistente por construcción, y
#: hay un test que lo ata (`test_el_codigo_arca_y_la_condicion_iva_nunca_se_contradicen`).
#:
#: Incluye ids que nuestro dominio todavía no produce (7 = No Categorizado, 8/9 = del Exterior,
#: 10 = Ley 19.640, 13/16 = monotributos especiales, 15 = No Alcanzado): están para que la
#: validación no rechace un caso legítimo el día que el vocabulario crezca.
CONDICIONES_VALIDAS_POR_LETRA: dict[str, frozenset[int]] = {
    "A": frozenset({1, 6, 13, 16}),
    "B": frozenset({4, 5, 7, 8, 9, 10, 15}),
    "C": frozenset({1, 4, 5, 6, 7, 8, 9, 10, 13, 15, 16}),
    "M": frozenset({1, 6, 13, 16}),
}

#: Conceptos (`Concepto` de WSFEv1). Una casa de repuestos vende productos; los otros dos entran
#: para no migrar el día que se facture un service.
CONCEPTO_PRODUCTOS = 1
CONCEPTO_SERVICIOS = 2
CONCEPTO_PRODUCTOS_Y_SERVICIOS = 3
CONCEPTOS: frozenset[int] = frozenset({1, 2, 3})

#: Moneda. El slice 1 factura solo en pesos y lo fija con un CHECK: una factura en dólares
#: necesita cotización del día contra ARCA, que es otro problema.
MONEDA_PESOS = "PES"
