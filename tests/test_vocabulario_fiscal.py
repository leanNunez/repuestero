"""El vocabulario fiscal: letra del comprobante, códigos de ARCA, documento del receptor.

Todo acá es función pura: no toca Postgres, no toca red, no necesita certificado. Es a propósito
—es la capa que se puede probar entera antes de que exista ninguna integración— y es la razón de
que este sea el primer PR de la cadena.

Los valores esperados están **hardcodeados**, nunca importados del módulo que se prueba. Un test
que hace `assert codigo_comprobante('FAC','A') == CODIGOS_COMPROBANTE[('FAC','A')]` lee la misma
tabla que el código y se queda verde aunque el número esté mal: no protege nada.
"""

from decimal import Decimal

import pytest

from app.core import arca, letra
from app.core.cond_fiscal import CONDICIONES_FISCALES, CONDICIONES_FISCALES_EMISOR
from app.core.documentos import DocumentoInvalido, documento_de

# --------------------------------------------------------------------------------------
# La letra
# --------------------------------------------------------------------------------------

#: La matriz COMPLETA emisor × receptor. Está entera y no de a casos sueltos porque el error que
#: importa (RI → MONOTRIBUTO debe ser A, no B) vive justamente en una celda que se saltea cuando
#: uno escribe "tres casos representativos".
MATRIZ_LETRA = [
    ("RESPONSABLE_INSCRIPTO", "RESPONSABLE_INSCRIPTO", "A"),
    ("RESPONSABLE_INSCRIPTO", "MONOTRIBUTO", "A"),
    ("RESPONSABLE_INSCRIPTO", "EXENTO", "B"),
    ("RESPONSABLE_INSCRIPTO", "CONSUMIDOR_FINAL", "B"),
    ("MONOTRIBUTO", "RESPONSABLE_INSCRIPTO", "C"),
    ("MONOTRIBUTO", "MONOTRIBUTO", "C"),
    ("MONOTRIBUTO", "EXENTO", "C"),
    ("MONOTRIBUTO", "CONSUMIDOR_FINAL", "C"),
    ("EXENTO", "RESPONSABLE_INSCRIPTO", "C"),
    ("EXENTO", "MONOTRIBUTO", "C"),
    ("EXENTO", "EXENTO", "C"),
    ("EXENTO", "CONSUMIDOR_FINAL", "C"),
]


@pytest.mark.parametrize(("emisor", "receptor", "esperada"), MATRIZ_LETRA)
def test_la_letra(emisor: str, receptor: str, esperada: str) -> None:
    assert letra.letra_de(emisor, receptor) == esperada


def test_un_monotributista_recibe_A_de_un_responsable_inscripto() -> None:
    """El caso que más se equivoca, con nombre propio para que se lea en el reporte.

    Un monotributista no computa crédito fiscal, y de ahí sale la intuición —equivocada— de que
    le corresponde B. Le corresponde A. Y el error es SILENCIOSO: ARCA no rechaza una B, así que
    no se descubre al emitir sino en una inspección, meses después.
    """
    assert letra.letra_de("RESPONSABLE_INSCRIPTO", "MONOTRIBUTO") == "A"


@pytest.mark.parametrize("receptor", sorted(CONDICIONES_FISCALES))
def test_un_consumidor_final_no_puede_emitir(receptor: str) -> None:
    with pytest.raises(letra.EmisorInvalido):
        letra.letra_de("CONSUMIDOR_FINAL", receptor)


def test_un_emisor_inventado_no_pasa() -> None:
    with pytest.raises(letra.EmisorInvalido):
        letra.letra_de("RESPONSABLE_NO_INSCRIPTO", "CONSUMIDOR_FINAL")


def test_un_receptor_inventado_no_pasa() -> None:
    with pytest.raises(letra.ReceptorInvalido):
        letra.letra_de("RESPONSABLE_INSCRIPTO", "MONOTRIBUTISTA")


def test_la_matriz_cubre_todas_las_combinaciones_posibles() -> None:
    """Candado del propio test: si mañana entra una condición fiscal nueva, este se pone rojo.

    Sin esto, ampliar `CONDICIONES_FISCALES` dejaría una fila sin probar y nadie se enteraría.
    """
    esperadas = {(e, r) for e in CONDICIONES_FISCALES_EMISOR for r in CONDICIONES_FISCALES}
    probadas = {(e, r) for e, r, _ in MATRIZ_LETRA}
    assert probadas == esperadas


def test_los_emisores_validos_son_UNA_lista_no_dos() -> None:
    """`letra.EMISORES_VALIDOS` es un alias, no una copia.

    Con dos listas, sumar un emisor a una sola dejaba a `letra_de` aceptándolo y devolviendo "C",
    mientras el test de arriba seguía verde porque arma sus expectativas desde la OTRA lista. Un
    `==` no alcanza para atajarlo: dos copias con el mismo contenido pasan igual. Por eso `is`.
    """
    assert letra.EMISORES_VALIDOS is CONDICIONES_FISCALES_EMISOR


def test_letra_de_nunca_devuelve_una_M() -> None:
    """La M la decide ARCA (RG 1575), no se deriva de las condiciones fiscales.

    Está en `LETRAS` porque hay que poder procesarla, pero nunca sale de acá.
    """
    derivadas = {
        letra.letra_de(e, r) for e in CONDICIONES_FISCALES_EMISOR for r in CONDICIONES_FISCALES
    }
    assert derivadas <= letra.LETRAS_DERIVABLES
    assert "M" not in derivadas


def test_la_M_es_una_letra_manejable_aunque_no_derivable() -> None:
    """Una validación escrita como `if letra in LETRAS` tiene que aceptar una M legítima."""
    assert "M" in letra.LETRAS
    assert "M" not in letra.LETRAS_DERIVABLES


# --------------------------------------------------------------------------------------
# El invariante cruzado
# --------------------------------------------------------------------------------------


def test_el_codigo_arca_y_la_condicion_iva_nunca_se_contradicen() -> None:
    """El único test que ata las dos tablas de `arca.py` entre sí.

    `COND_IVA_RECEPTOR` y `CONDICIONES_VALIDAS_POR_LETRA` se escribieron por separado, mirando el
    mismo manual. Nada garantiza que digan lo mismo salvo esto: para toda combinación que el
    dominio pueda producir, la condición del receptor tiene que estar permitida en la letra que le
    tocó. Cambiar una celda de la matriz de letras sin tocar la de condiciones lo pone rojo.
    """
    for emisor in CONDICIONES_FISCALES_EMISOR:
        for receptor in CONDICIONES_FISCALES:
            la_letra = letra.letra_de(emisor, receptor)
            id_condicion = arca.COND_IVA_RECEPTOR[receptor]
            permitidos = arca.CONDICIONES_VALIDAS_POR_LETRA[la_letra]

            assert id_condicion in permitidos, (
                f"{emisor} facturando a {receptor} da letra {la_letra}, "
                f"pero la condición {id_condicion} no está permitida en esa letra."
            )


def test_toda_condicion_fiscal_tiene_su_id_de_arca() -> None:
    """Sin esto, agregar una condición al vocabulario rompería recién al facturar."""
    assert set(arca.COND_IVA_RECEPTOR) == set(CONDICIONES_FISCALES)


# --------------------------------------------------------------------------------------
# Códigos de comprobante y numeración
# --------------------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("clase", "letra_cbte", "codigo"),
    [
        ("FAC", "A", 1),
        ("FAC", "B", 6),
        ("FAC", "C", 11),
        ("NC", "A", 3),
        ("NC", "B", 8),
        ("NC", "C", 13),
        ("ND", "A", 2),
        ("ND", "B", 7),
        ("ND", "C", 12),
    ],
)
def test_el_codigo_de_comprobante(clase: str, letra_cbte: str, codigo: int) -> None:
    assert arca.codigo_comprobante(clase, letra_cbte) == codigo


def test_una_combinacion_sin_codigo_electronico_levanta() -> None:
    with pytest.raises(arca.ComprobanteNoFiscal):
        arca.codigo_comprobante("REC", "A")  # un recibo no se autoriza ante ARCA


def test_factura_A_y_factura_B_no_comparten_espacio_de_numeracion() -> None:
    """El bug latente que este PR viene a evitar.

    ARCA exige un talonario independiente por (punto de venta, tipo de comprobante): la Factura A
    y la Factura B del mismo punto de venta arrancan las DOS en 1. Si la clave del numerador
    colapsara las dos en `'FAC'`, el segundo comprobante enviado se llevaría un rechazo por número
    fuera de secuencia — y los comprobantes emitidos no se renumeran.
    """
    clave_a = arca.clave_numeracion(arca.codigo_comprobante("FAC", "A"))
    clave_b = arca.clave_numeracion(arca.codigo_comprobante("FAC", "B"))

    assert clave_a == "FE001"
    assert clave_b == "FE006"
    assert clave_a != clave_b


@pytest.mark.parametrize("clave_no_fiscal", ["FAC", "NC", "REC", "OP", "CLI"])
def test_la_clave_fiscal_no_pisa_ninguna_clave_existente(clave_no_fiscal: str) -> None:
    """Los contadores fiscales conviven con los que ya están en `numeradores`."""
    fiscales = {arca.clave_numeracion(c) for c in arca.CODIGOS_VALIDOS}
    assert clave_no_fiscal not in fiscales


def test_la_clave_de_numeracion_entra_en_la_columna() -> None:
    """`numeradores.tipo` es `String(10)`: una clave más larga rompería al insertar."""
    assert all(len(arca.clave_numeracion(c)) <= 10 for c in arca.CODIGOS_VALIDOS)


# --------------------------------------------------------------------------------------
# Alícuotas
# --------------------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("porcentaje", "id_arca"),
    [
        (Decimal("0"), 3),
        (Decimal("10.50"), 4),
        (Decimal("21.00"), 5),
        (Decimal("27.00"), 6),
        (Decimal("5.00"), 8),
        (Decimal("2.50"), 9),
    ],
)
def test_el_id_de_alicuota(porcentaje: Decimal, id_arca: int) -> None:
    assert arca.id_alicuota(porcentaje) == id_arca


@pytest.mark.parametrize("inventada", [Decimal("15"), Decimal("21.5"), Decimal("-21")])
def test_una_alicuota_que_arca_no_acepta_levanta(inventada: Decimal) -> None:
    """Hoy `alicuota_iva` es un `Numeric(5,2)` libre: acepta 15% sin chistar.

    El 15% no aparece hasta que ARCA rechaza el comprobante. Esta es la primera reja; la segunda
    es el CHECK de la migración 0015.
    """
    with pytest.raises(arca.AlicuotaNoFiscal):
        arca.id_alicuota(inventada)


def test_la_alicuota_del_catalogo_matchea_sin_importar_la_escala() -> None:
    """`Numeric(5,2)` devuelve `Decimal('21.00')`, pero un literal suele escribirse `Decimal('21')`.

    Si el dict indexara por string o por float, uno de los dos no encontraría su id.
    """
    assert arca.id_alicuota(Decimal("21")) == arca.id_alicuota(Decimal("21.00")) == 5


def test_el_iva_no_gravado_y_el_exento_no_estan_entre_las_alicuotas() -> None:
    """Los ids 1 y 2 de ARCA no viajan en el array `Iva` sino en `ImpTotConc`/`ImpOpEx`."""
    assert 1 not in arca.ALICUOTAS_ARCA.values()
    assert 2 not in arca.ALICUOTAS_ARCA.values()


# --------------------------------------------------------------------------------------
# Documento del receptor
# --------------------------------------------------------------------------------------


def test_el_documento_explicito_le_gana_al_cuit() -> None:
    """Un consumidor final con DNI cargado viaja como DNI, no como anónimo ni como CUIT."""
    assert documento_de(doc_tipo=96, doc_nro="30111222", cuit="20-30111222-3") == (96, "30111222")


def test_sin_documento_explicito_se_declara_el_cuit_sin_guiones() -> None:
    """ARCA quiere los once dígitos pelados; en la base el CUIT vive formateado."""
    assert documento_de(cuit="30-71234567-8") == (80, "30712345678")


def test_sin_ningun_dato_se_declara_sin_identificar() -> None:
    assert documento_de() == (99, "0")


def test_un_doc_tipo_sin_numero_no_se_declara_a_medias() -> None:
    """Mandar el tipo con el número vacío es un rechazo garantizado: se cae al siguiente escalón."""
    assert documento_de(doc_tipo=96, doc_nro=None, cuit="20-30111222-3") == (80, "20301112223")
    assert documento_de(doc_tipo=96, doc_nro="") == (99, "0")


def test_un_numero_sin_tipo_no_se_puede_declarar() -> None:
    """Ocho dígitos sueltos no dicen si son un DNI o un pasaporte: se baja al escalón siguiente."""
    assert documento_de(doc_nro="30111222", cuit="20-30111222-3") == (80, "20301112223")
    assert documento_de(doc_nro="30111222") == (99, "0")


@pytest.mark.parametrize(
    ("crudo", "limpio"),
    [("30.111.222", "30111222"), ("30 111 222", "30111222"), ("30-111-222", "30111222")],
)
def test_el_numero_de_documento_viaja_sin_puntos_ni_guiones(crudo: str, limpio: str) -> None:
    """El mostrador escribe "30.111.222" todo el tiempo, y ARCA quiere el número pelado.

    La normalización se aplicaba solo al CUIT: un DNI con puntos viajaba tal cual y era rechazo.
    """
    assert documento_de(doc_tipo=96, doc_nro=crudo) == (96, limpio)


def test_el_tipo_sin_identificar_siempre_declara_numero_cero() -> None:
    """El 99 con cualquier número que no sea 0 es rechazo de ARCA.

    Pasa cuando alguien carga un cliente anónimo y el front manda el tipo con un número residual.
    Normalizarlo acá sale gratis; descubrirlo con el cliente ya afuera, no.
    """
    assert documento_de(doc_tipo=99, doc_nro="12345") == (99, "0")
    assert documento_de(doc_tipo=99, doc_nro="0") == (99, "0")


def test_un_tipo_de_documento_inventado_no_pasa() -> None:
    with pytest.raises(DocumentoInvalido):
        documento_de(doc_tipo=42, doc_nro="30111222")


# --------------------------------------------------------------------------------------
# Declaración de IVA ante ARCA
# --------------------------------------------------------------------------------------


def test_una_factura_C_no_declara_iva() -> None:
    """ARCA exige `ImpIVA=0`, `ImpNeto=ImpTotal` y el array de alícuotas VACÍO en una C.

    Mandar alícuotas en una C es rechazo directo, y es el error que se cuela cuando el mismo
    código arma las tres letras sin preguntar cuál es.
    """
    assert letra.declara_iva("C") is False


@pytest.mark.parametrize("con_iva", ["A", "B", "M"])
def test_las_letras_que_declaran_iva(con_iva: str) -> None:
    assert letra.declara_iva(con_iva) is True


def test_la_B_se_declara_con_iva_aunque_no_lo_muestre_desglosado() -> None:
    """El concepto que se confunde: "discriminar" es de IMPRESIÓN, "declarar" es de REQUEST.

    La B lleva el IVA incluido en el precio que ve el cliente, pero ante ARCA viaja con su neto,
    su IVA y sus alícuotas, igual que la A. Tratarla como una C —sin alícuotas— es un rechazo.
    """
    assert letra.declara_iva("B") is True


def test_una_letra_inventada_no_pasa() -> None:
    with pytest.raises(ValueError, match="no es una letra"):
        letra.declara_iva("X")
