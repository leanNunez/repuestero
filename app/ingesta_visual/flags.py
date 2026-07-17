"""Las reglas que deciden qué renglón necesita ojo humano. Puras: sin DB, sin LLM, sin red.

La premisa de este módulo: **la confianza que un LLM se auto-reporta está mal calibrada**.
Un modelo puede decir 0.95 sobre un número que leyó mal. Por eso `baja_confianza` es apenas
una de las reglas, y las que de verdad cazan errores son OBJETIVAS — comparan lo extraído
contra lo que el sistema ya sabe (`salto_de_costo`) o contra sí mismo (`no_cuadra`,
`duplicado`). Esas no dependen de la opinión del modelo sobre su propio trabajo.

Ninguna de estas reglas bloquea nada. Marcan. El que decide es el humano.
"""

from collections import Counter
from decimal import Decimal

from app.ingesta_visual.schemas import Flag, RenglonExtraido

#: Un costo que se movió más de esto respecto del que ya estaba, en cualquier dirección,
#: se marca. No es "un aumento grande": es el síntoma clásico de un OCR que leyó
#: "1.234,50" como "123450". Los aumentos reales también se marcan, y está bien: en una
#: repuestera un salto de costo del 50% es una decisión, no un trámite.
UMBRAL_SALTO_COSTO = Decimal("0.5")

#: Tolerancia del checksum contra el total impreso en el papel. 1% cubre el redondeo del
#: proveedor sin dejar pasar un renglón mal leído.
TOLERANCIA_TOTAL = Decimal("0.01")


def flags_de_renglon(
    renglon: RenglonExtraido,
    *,
    costo_actual: Decimal | None,
    tiene_listas: bool,
    tiene_margen: bool,
    es_alta: bool,
    duplicado: bool,
    texto_sospechoso: bool,
    umbral_confianza: float,
) -> list[Flag]:
    """Todos los motivos por los que este renglón merece una mirada, en orden de gravedad."""
    flags: list[Flag] = []

    if not (renglon.codigo or "").strip():
        flags.append("sin_codigo")

    if texto_sospechoso:
        flags.append("texto_sospechoso")

    if duplicado:
        flags.append("duplicado")

    if renglon.costo_unitario == 0:
        flags.append("costo_cero")

    if costo_actual is not None and costo_actual > 0:
        salto = abs(renglon.costo_unitario - costo_actual) / costo_actual
        if salto > UMBRAL_SALTO_COSTO:
            flags.append("salto_de_costo")

    if es_alta:
        # Un artículo nuevo no tiene margen guardado, y no se inventa uno. Se crea sin
        # precio de venta y alguien tiene que ponérselo.
        flags.append("alta_sin_precio")
    else:
        if not tiene_listas:
            flags.append("sin_listas")
        elif not tiene_margen:
            flags.append("sin_margen")

    if renglon.confianza < umbral_confianza:
        flags.append("baja_confianza")

    return flags


def incluir_por_defecto(flags: list[Flag]) -> bool:
    """Si el front debería arrancar con este renglón tildado.

    Solo dos flags apagan el check, y ambos comparten una propiedad: el renglón no se puede
    escribir bien tal como está. Sin código no hay artículo que crear; con texto sospechoso
    hay que leerlo antes de meterlo en la base. Para todo lo demás el default es incluir —
    marcar todo apagado entrenaría a la gente a tildar sin mirar, que es peor que no marcar.
    """
    return not any(f in flags for f in ("sin_codigo", "texto_sospechoso"))


def codigos_duplicados(renglones: list[RenglonExtraido]) -> set[str]:
    """Códigos que aparecen más de una vez en el MISMO remito.

    Puede ser legítimo (el mismo artículo en dos renglones con distinto costo) o un error de
    lectura. No se decide acá: se marca y se muestra.
    """
    cuenta = Counter((r.codigo or "").strip() for r in renglones if (r.codigo or "").strip())
    return {codigo for codigo, n in cuenta.items() if n > 1}


def total_calculado(renglones: list[RenglonExtraido]) -> Decimal:
    return sum((r.cantidad * r.costo_unitario for r in renglones), start=Decimal("0")).quantize(
        Decimal("0.01")
    )


def advertencias_de_remito(
    renglones: list[RenglonExtraido], total_declarado: Decimal | None
) -> list[str]:
    """Problemas del remito como conjunto, no de un renglón suelto.

    `no_cuadra` es la regla más valiosa de todo el módulo: el papel trae un total escrito, y
    si la suma de lo que leímos no da ese total, algo se leyó mal — sin necesidad de saber
    QUÉ. Es un checksum que viene gratis con el documento.
    """
    avisos: list[str] = []

    if not renglones:
        avisos.append("No se reconoció ningún renglón en la imagen.")
        return avisos

    if total_declarado is not None and total_declarado > 0:
        calculado = total_calculado(renglones)
        diferencia = abs(calculado - total_declarado) / total_declarado
        if diferencia > TOLERANCIA_TOTAL:
            avisos.append(
                f"La suma de los renglones (${calculado}) no coincide con el total del "
                f"remito (${total_declarado}). Revisá cantidades y costos."
            )

    dups = codigos_duplicados(renglones)
    if dups:
        avisos.append(f"Códigos repetidos en el remito: {', '.join(sorted(dups))}.")

    return avisos
