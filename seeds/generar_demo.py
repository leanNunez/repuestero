"""Genera el seed DEMO realista en seeds/demo/ (CSVs que el importador consume).

No son datos reales de ningún comercio (no los tenemos todavía), pero tienen la FORMA y las
asperezas del dato verdadero de una casa de repuestos argentina. El legacy tenía ~2.000
productos y ~900 clientes (docs/analisis-legacy.md §1): con veinte filas de prueba la demo
parece un TP; con dos mil parece un negocio. Por eso este seed es HÍBRIDO:

  - Un núcleo CURADO A MANO (los ~20 "héroes"): filtros y correas que existen de verdad,
    con compatibilidad vehículo-repuesto validada. Son los que aguantan que alguien los
    googlee, y los que se muestran en detalle cuando se demuestra el diferencial.
  - Un relleno PROCEDURAL hasta ~2.000 artículos y ~900 clientes: marcas y rubros reales,
    códigos PLAUSIBLES (respetan el patrón de cada fabricante —Mann arranca con W/C/WK, NGK
    sus bujías con letras+números— aunque el código puntual sea inventado), precios 2026 en
    pesos, CUITs con dígito verificador válido, y compatibilidad mezclando dato confirmado a
    mano con sugerencias de IA sin confirmar (la razón de ser de las columnas origen/confirmado).

Por qué un generador y no CSVs a mano: a mano no llegás a 2.000. Y la integridad referencial
entre los diez archivos (cada articulo_codigo de precios/stock/aplicaciones tiene que existir
en articulos, cada aplicación apunta a un vehículo que existe) queda garantizada POR
CONSTRUCCIÓN. El azar va con semilla fija (`random.Random`): dos corridas producen bytes
idénticos, así el diff en git queda limpio y el seed es reproducible.

    python seeds/generar_demo.py        # reescribe seeds/demo/*.csv
    python -m app.importador --crear-org "Casa Demo" --source seeds/demo

Los CSVs generados se versionan igual: son el artefacto que consume el importador y espejan
la forma de un export de Paradox (Fase 2).
"""

import csv
import random
import re
from decimal import ROUND_HALF_UP, Decimal
from pathlib import Path

DESTINO = Path(__file__).parent / "demo"

# Semilla fija: el seed es data de demo, pero el ARCHIVO es un artefacto versionado. Con azar
# reproducible, `git diff` solo muestra cambios cuando cambia el generador, no en cada corrida.
rng = random.Random(20260720)

OBJETIVO_ARTICULOS = 2000
OBJETIVO_CLIENTES = 900

_PESOS_CUIT = (5, 4, 3, 2, 7, 6, 5, 4, 3, 2)


def cuit(prefijo: str, medio: str) -> str:
    """Arma un CUIT con dígito verificador módulo 11 (mismo algoritmo que valida el service)."""
    digitos = [int(d) for d in f"{prefijo}{medio}"]
    resto = sum(a * b for a, b in zip(digitos, _PESOS_CUIT, strict=True)) % 11
    verificador = 0 if resto == 0 else 11 - resto
    verificador = 9 if verificador == 10 else verificador
    return f"{prefijo}-{medio}-{verificador}"


def _redondear(valor: Decimal) -> Decimal:
    return valor.quantize(Decimal("1"), rounding=ROUND_HALF_UP)


# --------------------------------------------------------------------------- listas y depósitos
LISTAS = [
    ("MOST", "Lista Mostrador"),
    ("MAY", "Lista Mayorista"),
    ("TALL", "Lista Taller"),
]

DEPOSITOS = [
    ("CEN", "Depósito Central"),
    ("MOS", "Mostrador"),
]

# Margen sobre costo por lista. Mostrador el más caro, mayorista el más barato.
MARGEN_LISTA = {"MOST": Decimal("62"), "TALL": Decimal("48"), "MAY": Decimal("30")}

# Rubros que un taller compra (llevan lista TALL además de MOST/MAY).
RUBROS_TALLER = {"FILTROS", "CORREAS", "ENCENDIDO", "FRENOS", "LUBRICANTES"}

# --------------------------------------------------------------------------- artículos HÉROES
# Curados a mano: part numbers REALES, con compatibilidad validada más abajo. Son la cara del
# diferencial. El resto del catálogo se genera proceduralmente para llegar a ~2.000.
# (codigo, detalle, costo, iva, punto_pedido, marca, rubro, codigo_barra)
HERO_ARTICULOS = [
    ("W719/80", "FILTRO DE ACEITE MANN W719/80", 9800, 21, 6, "Mann", "FILTROS", "7791234500011"),
    ("PH5566", "FILTRO DE ACEITE FRAM PH5566", 7200, 21, 8, "Fram", "FILTROS", "7791234500028"),
    ("C25114", "FILTRO DE AIRE MANN C25114", 14500, 21, 4, "Mann", "FILTROS", "7791234500035"),
    (
        "WK814/1",
        "FILTRO DE COMBUSTIBLE MANN WK814/1",
        18200,
        21,
        3,
        "Mann",
        "FILTROS",
        "7791234500042",
    ),
    (
        "CU2545",
        "FILTRO DE HABITACULO MANN CU2545",
        12800,
        21,
        5,
        "Mann",
        "FILTROS",
        "7791234500059",
    ),
    ("5PK1123", "CORREA POLY-V GATES 5PK1123", 15600, 21, 4, "Gates", "CORREAS", "7791234500066"),
    ("94048", "KIT DISTRIBUCION DAYCO 94048", 89400, 21, 2, "Dayco", "CORREAS", "7791234500073"),
    ("BKR6E", "BUJIA NGK BKR6E", 4200, 21, 24, "NGK", "ENCENDIDO", "7791234500080"),
    ("FR7DC", "BUJIA BOSCH FR7DC+", 4800, 21, 16, "Bosch", "ENCENDIDO", "7791234500097"),
    (
        "FDB1617",
        "PASTILLA FRENO DELANT FERODO FDB1617",
        32500,
        21,
        4,
        "Ferodo",
        "FRENOS",
        "7791234500103",
    ),
    ("N1055", "PASTILLA FRENO COBREQ N1055", 24800, 21, 5, "Cobreq", "FRENOS", "7791234500110"),
    (
        "G16789",
        "AMORTIGUADOR DELANT MONROE G16789",
        68900,
        21,
        2,
        "Monroe",
        "SUSPENSION",
        "7791234500127",
    ),
    (
        "30125",
        "AMORTIGUADOR TRASERO SADAR 30125",
        52300,
        21,
        2,
        "Sadar",
        "SUSPENSION",
        "7791234500134",
    ),
    (
        "ELAION-F30",
        "ACEITE YPF ELAION F30 5W30 X4L",
        38500,
        21,
        6,
        "YPF",
        "LUBRICANTES",
        "7791234500141",
    ),
    (
        "HELIX-HX7",
        "ACEITE SHELL HELIX HX7 10W40 X4L",
        41200,
        21,
        5,
        "Shell",
        "LUBRICANTES",
        "7791234500158",
    ),
    ("6204-2RS", "RODAMIENTO SKF 6204 2RS", 6800, 21, 12, "SKF", "RODAMIENTOS", "7791234500165"),
    (
        "VKBA3550",
        "MAZA RUEDA C/RODAMIENTO SKF VKBA3550",
        45600,
        21,
        3,
        "SKF",
        "RODAMIENTOS",
        "7791234500172",
    ),
    (
        "H4-12V",
        "LAMPARA OSRAM H4 12V 60/55W",
        3900,
        21,
        24,
        "Osram",
        "ILUMINACION",
        "7791234500189",
    ),
    (
        "H7-12V",
        "LAMPARA PHILIPS H7 12V 55W",
        4300,
        21,
        20,
        "Philips",
        "ILUMINACION",
        "7791234500196",
    ),
    ("KYB334", "ESPIRAL SUSPENSION KYB RA3341", 27800, 21, 3, "KYB", "SUSPENSION", "7791234500202"),
]

# --------------------------------------------------------------------------- motor procedural
# Cada marca tiene su patrón de código. La clave de la plausibilidad: un código generado
# RESPETA el formato del fabricante (Mann → W###/##, NGK → letras+números) aunque la pieza
# puntual no exista. `XYZ-999` gritaría "dato falso"; `W714/33` pasa desapercibido en una
# grilla de 2.000 filas. El detalle de cada rubro va abajo.
PATRONES = {
    "Mann": lambda r: r.choice(
        [
            f"W{r.randint(610, 950)}/{r.randint(1, 80)}",
            f"C{r.randint(1100, 3600)}",
            f"WK{r.randint(31, 999)}",
            f"CU{r.randint(1600, 3900)}",
        ]
    ),
    "Fram": lambda r: r.choice([f"PH{r.randint(3000, 9999)}", f"CA{r.randint(3200, 9800)}"]),
    "Wega": lambda r: r.choice([f"JFC{r.randint(100, 999)}", f"WO{r.randint(1000, 9999)}"]),
    "Mahle": lambda r: r.choice([f"OC{r.randint(80, 999)}", f"LX{r.randint(100, 3200)}"]),
    "Bosch": lambda r: r.choice(
        [f"0986{r.choice(['AF', 'B0', 'TB'])}{r.randint(1000, 9999)}", f"FR{r.randint(5, 8)}DC"]
    ),
    "Gates": lambda r: r.choice(
        [
            f"{r.randint(3, 8)}PK{r.randint(700, 2200)}",
            f"K0{r.randint(15, 60)}{r.randint(300, 650)}",
        ]
    ),
    "Dayco": lambda r: r.choice([f"{r.randint(90000, 96000)}", f"KTB{r.randint(100, 900)}"]),
    "Bando": lambda r: f"{r.randint(4, 7)}PK{r.randint(700, 2100)}",
    "Contitech": lambda r: r.choice([f"CT{r.randint(700, 1200)}", f"6PK{r.randint(1000, 2200)}"]),
    "NGK": lambda r: r.choice(
        [f"BKR{r.randint(5, 7)}E", f"BPR{r.randint(5, 6)}ES", f"DCPR{r.randint(6, 8)}E"]
    ),
    "Denso": lambda r: r.choice([f"K{r.randint(16, 20)}PR-U", f"IK{r.randint(16, 22)}"]),
    "Ferodo": lambda r: r.choice([f"FDB{r.randint(1000, 2100)}", f"FVR{r.randint(1000, 2100)}"]),
    "Cobreq": lambda r: r.choice([f"N{r.randint(500, 1600)}", f"NF{r.randint(100, 900)}"]),
    "TRW": lambda r: r.choice([f"GDB{r.randint(1000, 2200)}", f"JTE{r.randint(100, 999)}"]),
    "Fremax": lambda r: f"BD{r.randint(4000, 6000)}",
    "Monroe": lambda r: r.choice([f"G{r.randint(16000, 17000)}", f"E{r.randint(1000, 1999)}"]),
    "Sadar": lambda r: f"{r.randint(28000, 33000)}",
    "KYB": lambda r: r.choice([f"{r.randint(333000, 335999)}", f"RA{r.randint(3000, 3999)}"]),
    "Corven": lambda r: f"CV{r.randint(1000, 9999)}",
    "Ciccarelli": lambda r: f"{r.randint(1000, 4999)}",
    "SKF": lambda r: r.choice(
        [
            f"{r.randint(6000, 6410)}-2RS",
            f"VKBA{r.randint(3400, 3900)}",
            f"VKM{r.randint(11000, 13999)}",
        ]
    ),
    "NSK": lambda r: f"{r.randint(6000, 6410)}DDU",
    "INA": lambda r: f"F-{r.randint(100000, 599999)}",
    "FAG": lambda r: f"{r.randint(529000, 713999)}",
    "Osram": lambda r: r.choice([f"64{r.randint(150, 215)}", f"H{r.choice([1, 3, 4, 7, 11])}-12V"]),
    "Philips": lambda r: r.choice([f"12{r.randint(258, 972)}", f"H{r.choice([1, 4, 7, 11])}-12V"]),
    "Narva": lambda r: f"{r.randint(48000, 48999)}",
    "Sachs": lambda r: f"3000{r.randint(100, 999)}{r.randint(100, 999)}",
    "Luk": lambda r: f"6{r.randint(18, 64)}{r.randint(1000, 3999)}00",
    "Valeo": lambda r: f"{r.randint(801000, 826999)}",
    "Vulco": lambda r: f"VB-{r.randint(1000, 4999)}",
    "DPH": lambda r: f"DPH{r.randint(1000, 9999)}",
    "Behr": lambda r: f"CT{r.randint(10, 20)}000",
    "Moura": lambda r: f"M{r.randint(18, 28)}{r.choice(['ED', 'FD', 'KD'])}",
    "Willard": lambda r: f"{r.randint(12, 110)}{r.choice(['LE', 'LD', 'HE'])}",
    "Illinois": lambda r: f"{r.randint(20000, 29999)}",
    "Taranto": lambda r: f"{r.randint(2000, 4999)}",
    "DPA": lambda r: f"DPA{r.randint(1000, 9999)}",
}


def _codigo(marca: str, r: random.Random) -> str:
    patron = PATRONES.get(marca)
    if patron:
        return patron(r)
    # Marca sin patrón propio: prefijo de sus letras + número. Sigue leyéndose como un código.
    prefijo = re.sub(r"[^A-Z]", "", marca.upper())[:3] or "RX"
    return f"{prefijo}{r.randint(100, 99999)}"


def _punto_pedido(costo: int, r: random.Random) -> int:
    """Cuanto más caro el ítem, menos stock mínimo se banca tener. Espeja la realidad."""
    if costo >= 60000:
        return r.choice([2, 3, 4])
    if costo >= 25000:
        return r.choice([3, 4, 5, 6])
    if costo >= 10000:
        return r.choice([6, 8, 10])
    return r.choice([12, 16, 20, 24])


# (rubro, peso_relativo, [marcas], [tipos de detalle], (costo_min, costo_max))
# El peso reparte los ~1.980 artículos generados: en una casa de repuestos hay muchos más
# filtros y frenos que juntas. Los tipos arman el detalle: "{tipo} {MARCA} {codigo}".
RUBROS = [
    (
        "FILTROS",
        16,
        ["Mann", "Fram", "Wega", "Mahle", "Bosch"],
        ["FILTRO DE ACEITE", "FILTRO DE AIRE", "FILTRO DE COMBUSTIBLE", "FILTRO DE HABITACULO"],
        (5000, 22000),
    ),
    (
        "FRENOS",
        12,
        ["Ferodo", "Cobreq", "TRW", "Fremax"],
        ["PASTILLA FRENO DELANT", "PASTILLA FRENO TRAS", "DISCO FRENO DELANT", "CAMPANA FRENO"],
        (18000, 46000),
    ),
    (
        "SUSPENSION",
        11,
        ["Monroe", "Sadar", "KYB", "Corven", "Ciccarelli"],
        [
            "AMORTIGUADOR DELANT",
            "AMORTIGUADOR TRAS",
            "ESPIRAL SUSPENSION",
            "ROTULA SUSPENSION",
            "BIELETA BARRA ESTAB",
            "EXTREMO DIRECCION",
        ],
        (18000, 92000),
    ),
    (
        "ELECTRICIDAD",
        8,
        ["Moura", "Willard", "Bosch", "Valeo"],
        ["BATERIA", "ALTERNADOR", "MOTOR ARRANQUE", "REGULADOR VOLTAJE"],
        (40000, 260000),
    ),
    (
        "RODAMIENTOS",
        8,
        ["SKF", "NSK", "INA", "FAG"],
        ["RODAMIENTO", "MAZA RUEDA C/RODAMIENTO", "CRAPODINA", "RULEMAN RUEDA"],
        (5000, 62000),
    ),
    (
        "ENCENDIDO",
        7,
        ["NGK", "Bosch", "Denso"],
        ["BUJIA", "CABLE BUJIA JUEGO", "BOBINA ENCENDIDO"],
        (3500, 42000),
    ),
    (
        "CORREAS",
        6,
        ["Gates", "Dayco", "Bando", "Contitech"],
        ["CORREA POLY-V", "CORREA DISTRIBUCION", "KIT DISTRIBUCION", "TENSOR CORREA"],
        (12000, 96000),
    ),
    (
        "LUBRICANTES",
        6,
        ["YPF", "Shell", "Castrol", "Total", "Motul", "Valvoline"],
        ["ACEITE"],  # el detalle de lubricantes es especial, se arma aparte
        (28000, 56000),
    ),
    (
        "REFRIGERACION",
        6,
        ["Vulco", "Wega", "DPH", "Behr"],
        ["BOMBA DE AGUA", "TERMOSTATO", "RADIADOR", "ELECTROVENTILADOR"],
        (20000, 140000),
    ),
    (
        "ILUMINACION",
        6,
        ["Osram", "Philips", "Narva"],
        ["LAMPARA", "FARO DELANT", "OPTICA"],
        (3000, 48000),
    ),
    (
        "EMBRAGUE",
        5,
        ["Sachs", "Luk", "Valeo", "Corven"],
        ["KIT EMBRAGUE", "DISCO EMBRAGUE", "PLATO PRESION"],
        (60000, 190000),
    ),
    (
        "DIRECCION",
        5,
        ["Ciccarelli", "Corven", "TRW"],
        ["EXTREMO DIRECCION", "ROTULA DIRECCION", "CREMALLERA DIRECCION"],
        (15000, 90000),
    ),
    (
        "JUNTAS",
        4,
        ["Illinois", "Taranto"],
        ["JUNTA TAPA CILINDRO", "JUNTA TAPA VALVULA", "RETEN CIGUEÑAL", "KIT JUNTAS MOTOR"],
        (8000, 70000),
    ),
    (
        "TRANSMISION",
        4,
        ["SKF", "Corven", "DPA"],
        ["HOMOCINETICA", "PUNTA EJE", "CRUCETA CARDAN"],
        (25000, 120000),
    ),
]

# Aceites: nombre comercial por marca + viscosidad. Detalle "ACEITE {MARCA} {NOMBRE} {VISC} X4L".
LUBRICANTES = {
    "YPF": ["Elaion F30", "Elaion F50", "Elaion Moto"],
    "Shell": ["Helix HX5", "Helix HX7", "Helix Ultra", "Rimula R4"],
    "Castrol": ["GTX", "Magnatec", "Edge"],
    "Total": ["Quartz 5000", "Quartz 7000", "Quartz 9000"],
    "Motul": ["6100", "8100", "3000"],
    "Valvoline": ["MaxLife", "SynPower"],
}
VISCOSIDADES = ["5W30", "10W40", "15W40", "5W40", "20W50", "25W60"]


def generar_articulos() -> list[tuple]:
    """Héroes curados + relleno procedural hasta OBJETIVO_ARTICULOS, códigos únicos por org."""
    articulos = list(HERO_ARTICULOS)
    usados = {a[0] for a in articulos}
    barra = 2000000000  # los generados arrancan lejos del rango de los héroes: no colisionan

    faltan = OBJETIVO_ARTICULOS - len(articulos)
    total_peso = sum(spec[1] for spec in RUBROS)
    objetivos = {spec[0]: faltan * spec[1] // total_peso for spec in RUBROS}
    # El reparto entero deja un resto: se lo damos a los primeros rubros para clavar el total.
    resto = faltan - sum(objetivos.values())
    for spec in RUBROS[:resto]:
        objetivos[spec[0]] += 1

    for rubro, _peso, marcas, tipos, (cmin, cmax) in RUBROS:
        generados = 0
        intentos = 0
        while generados < objetivos[rubro] and intentos < objetivos[rubro] * 20 + 50:
            intentos += 1
            marca = rng.choice(marcas)

            if rubro == "LUBRICANTES":
                nombre = rng.choice(LUBRICANTES[marca])
                visc = rng.choice(VISCOSIDADES)
                codigo = f"{marca[:3].upper()}{visc}{rng.randint(10, 999)}"
                detalle = f"ACEITE {marca.upper()} {nombre.upper()} {visc} X4L"
            else:
                codigo = _codigo(marca, rng)
                detalle = f"{rng.choice(tipos)} {marca.upper()} {codigo}"

            if codigo in usados or len(codigo) > 40 or len(detalle) > 200:
                continue
            usados.add(codigo)

            costo = rng.randrange(cmin, cmax, 100)
            punto = _punto_pedido(costo, rng)
            barra += 1
            articulos.append((codigo, detalle, costo, 21, punto, marca, rubro, f"779{barra:010d}"))
            generados += 1

    return articulos


# --------------------------------------------------------------------------- proveedores
# Héroes (P01..P04) + distribuidores por rubro. Un negocio real compra a ~15-20 proveedores.
# (codigo, razon_social, prefijo_cuit, medio_cuit, telefono, email)
PROVEEDORES = [
    (
        "P01",
        "Distribuidora Autopartes del Litoral SA",
        "30",
        "71044569",
        "0342-4551200",
        "ventas@autolitoral.com.ar",
    ),
    (
        "P02",
        "Repuestos y Filtros Córdoba SRL",
        "30",
        "68522345",
        "0351-4889077",
        "pedidos@rfcordoba.com.ar",
    ),
    (
        "P03",
        "Importadora Rodamientos del Sur SA",
        "33",
        "70912888",
        "011-47125566",
        "info@rodasur.com.ar",
    ),
    (
        "P04",
        "Lubricantes y Accesorios Rosario SRL",
        "30",
        "64111222",
        "0341-4260880",
        "ventas@lubrirosario.com.ar",
    ),
    (
        "P05",
        "Bearings y Repuestos SA",
        "30",
        "70588431",
        "011-46339900",
        "ventas@bearingsrep.com.ar",
    ),
    (
        "P06",
        "Frenos del Centro SRL",
        "30",
        "69477215",
        "0351-4712233",
        "pedidos@frenoscentro.com.ar",
    ),
    (
        "P07",
        "Suspensiones Pergamino SA",
        "30",
        "71203366",
        "02477-421900",
        "ventas@suspergamino.com.ar",
    ),
    (
        "P08",
        "Electro Baterías Rosario SRL",
        "30",
        "65488120",
        "0341-4551800",
        "info@electrobat.com.ar",
    ),
    (
        "P09",
        "Distribuidora Nacional de Filtros SA",
        "33",
        "70744099",
        "011-43214455",
        "ventas@dnfiltros.com.ar",
    ),
    (
        "P10",
        "Iluminación Automotor SRL",
        "30",
        "68011744",
        "0341-4409988",
        "pedidos@iluautomotor.com.ar",
    ),
    (
        "P11",
        "Embragues y Transmisiones SA",
        "30",
        "71566082",
        "0351-4990011",
        "ventas@embtrans.com.ar",
    ),
    (
        "P12",
        "Refrigeración Automotriz del Litoral SRL",
        "30",
        "66922410",
        "0342-4560700",
        "info@refriauto.com.ar",
    ),
    (
        "P13",
        "Lubricentro Mayorista SA",
        "30",
        "70233158",
        "0341-4778800",
        "ventas@lubmayorista.com.ar",
    ),
    (
        "P14",
        "Autopartes Buenos Aires SA",
        "33",
        "71890044",
        "011-45667788",
        "pedidos@autopartesba.com.ar",
    ),
    (
        "P15",
        "Juntas y Retenes del Norte SRL",
        "30",
        "64300921",
        "0341-4223311",
        "ventas@juntasnorte.com.ar",
    ),
    (
        "P16",
        "Dirección y Tren Delantero SA",
        "30",
        "71100238",
        "0351-4880022",
        "info@direcciontren.com.ar",
    ),
]

# Qué proveedores surten cada rubro. El primero es el preferido. Los generados heredan esto.
RUBRO_PROVEEDORES = {
    "FILTROS": ["P09", "P01", "P02"],
    "FRENOS": ["P06", "P02"],
    "SUSPENSION": ["P07", "P01"],
    "ELECTRICIDAD": ["P08", "P14"],
    "RODAMIENTOS": ["P05", "P03"],
    "ENCENDIDO": ["P02", "P08"],  # encendido lo trae Córdoba y electricidad
    "CORREAS": ["P01", "P11"],
    "LUBRICANTES": ["P13", "P04"],
    "REFRIGERACION": ["P12", "P14"],
    "ILUMINACION": ["P10", "P02"],
    "EMBRAGUE": ["P11"],
    "DIRECCION": ["P16", "P07"],
    "JUNTAS": ["P15", "P02"],
    "TRANSMISION": ["P11", "P05"],
}

# --------------------------------------------------------------------------- clientes HÉROES
# (codigo, denominacion, cond_fiscal, prefijo_cuit, medio_cuit, limite, telefono, email, direccion)
HERO_CLIENTES = [
    (
        "C001",
        "Taller Mecánico El Rulo",
        "MONOTRIBUTO",
        "20",
        "28456789",
        500000,
        "0341-155667788",
        "elrulo@gmail.com",
        "Av. San Martín 2340, Rosario",
    ),
    (
        "C002",
        "Transporte La Veloz SA",
        "RESPONSABLE_INSCRIPTO",
        "30",
        "71233445",
        3000000,
        "0341-4780099",
        "compras@laveloz.com.ar",
        "Ruta 9 Km 312, Roldán",
    ),
    (
        "C003",
        "Rectificadora San Martín",
        "RESPONSABLE_INSCRIPTO",
        "27",
        "32118844",
        1200000,
        "0341-4551133",
        "rectisanmartin@hotmail.com",
        "Mendoza 1870, Rosario",
    ),
    (
        "C004",
        "Gomería y Repuestos Norte",
        "MONOTRIBUTO",
        "23",
        "30999111",
        400000,
        "0341-156443322",
        None,
        "Av. Alberdi 990, Rosario",
    ),
    ("C005", "García Marcelo", "CONSUMIDOR_FINAL", None, None, 0, "0341-153998877", None, None),
    ("C006", "Consumidor Final", "CONSUMIDOR_FINAL", None, None, 0, None, None, None),
]

# --------------------------------------------------------------------------- clientes procedural
NOMBRES_M = [
    "Juan",
    "Carlos",
    "Miguel",
    "Roberto",
    "Sergio",
    "Daniel",
    "Marcelo",
    "Gustavo",
    "Fernando",
    "Diego",
    "Pablo",
    "Luis",
    "Jorge",
    "Raúl",
    "Héctor",
    "Oscar",
    "Ricardo",
    "Andrés",
    "Martín",
    "Gabriel",
    "Julio",
    "Rubén",
    "Mario",
    "Claudio",
    "Néstor",
    "Federico",
    "Lucas",
    "Matías",
    "Nicolás",
    "Facundo",
    "Leandro",
    "Cristian",
    "Franco",
]
NOMBRES_F = [
    "María",
    "Ana",
    "Laura",
    "Silvia",
    "Mónica",
    "Patricia",
    "Sandra",
    "Gabriela",
    "Verónica",
    "Carla",
    "Natalia",
    "Romina",
    "Cecilia",
    "Alejandra",
    "Susana",
    "Beatriz",
]
APELLIDOS = [
    "Gómez",
    "Fernández",
    "Rodríguez",
    "López",
    "Martínez",
    "García",
    "Pérez",
    "Sánchez",
    "Romero",
    "Sosa",
    "Torres",
    "Álvarez",
    "Ruiz",
    "Ramírez",
    "Flores",
    "Benítez",
    "Acosta",
    "Medina",
    "Herrera",
    "Aguirre",
    "Giménez",
    "Molina",
    "Silva",
    "Castro",
    "Rojas",
    "Ortiz",
    "Núñez",
    "Luna",
    "Cabrera",
    "Ríos",
    "Godoy",
    "Ferreyra",
    "Vega",
    "Correa",
    "Ponce",
    "Maidana",
    "Moreno",
    "Domínguez",
    "Peralta",
    "Villalba",
]
ZONAS = [
    "del Litoral",
    "del Centro",
    "Rosario",
    "San Lorenzo",
    "Roldán",
    "Funes",
    "Pergamino",
    "del Sur",
    "Norte",
    "Oeste",
    "San Nicolás",
    "Villa Constitución",
    "Cañada de Gómez",
    "Casilda",
]
CALLES = [
    "Av. San Martín",
    "Mendoza",
    "Córdoba",
    "Santa Fe",
    "Av. Pellegrini",
    "Bv. Oroño",
    "San Juan",
    "Rioja",
    "Av. Alberdi",
    "Av. Provincias Unidas",
    "Ovidio Lagos",
    "Av. Francia",
    "27 de Febrero",
    "Salta",
    "Tucumán",
]
CIUDADES = [
    "Rosario",
    "San Lorenzo",
    "Funes",
    "Roldán",
    "Pérez",
    "Villa Gobernador Gálvez",
    "Casilda",
    "Cañada de Gómez",
    "San Nicolás",
    "Pergamino",
]


def _telefono(r: random.Random) -> str | None:
    if r.random() < 0.15:
        return None
    if r.random() < 0.5:
        return f"0341-{r.randint(4000000, 4899999)}"
    return f"0341-15{r.randint(3000000, 6999999)}"


def _direccion(r: random.Random) -> str | None:
    if r.random() < 0.2:
        return None
    return f"{r.choice(CALLES)} {r.randint(100, 4900)}, {r.choice(CIUDADES)}"


def generar_clientes() -> list[tuple]:
    """Héroes + ~900 clientes: personas y comercios, cond_fiscal repartida, CUIT válido y único."""
    clientes = list(HERO_CLIENTES)
    medios_usados = {c[4] for c in clientes if c[4]}
    faltan = OBJETIVO_CLIENTES - len(clientes)

    def medio_unico() -> str:
        while True:
            m = f"{rng.randint(10000000, 99999999)}"
            if m not in medios_usados:
                medios_usados.add(m)
                return m

    for i in range(faltan):
        codigo = f"C{1000 + i:04d}"
        dado = rng.random()

        if dado < 0.30:  # consumidor final: persona, sin CUIT, sin cuenta corriente
            nombre = rng.choice(NOMBRES_M + NOMBRES_F)
            denom = f"{rng.choice(APELLIDOS)} {nombre}"
            clientes.append(
                (
                    codigo,
                    denom,
                    "CONSUMIDOR_FINAL",
                    None,
                    None,
                    0,
                    _telefono(rng),
                    None,
                    _direccion(rng),
                )
            )
            continue

        if dado < 0.65:  # monotributo: taller/gomería chico o persona
            plantilla = rng.choice(
                [
                    f"Taller Mecánico {rng.choice(APELLIDOS)}",
                    f"Gomería {rng.choice(APELLIDOS)}",
                    f"Taller {rng.choice(APELLIDOS)} Hnos",
                    f"{rng.choice(APELLIDOS)} {rng.choice(NOMBRES_M + NOMBRES_F)}",
                    f"Lubricentro {rng.choice(ZONAS)}",
                ]
            )
            prefijo = rng.choice(["20", "23", "27"])
            limite = rng.choice([200000, 300000, 400000, 500000, 800000])
            email = (
                f"{re.sub(r'[^a-z]', '', plantilla.lower())[:14]}@gmail.com"
                if rng.random() < 0.6
                else None
            )
            clientes.append(
                (
                    codigo,
                    plantilla,
                    "MONOTRIBUTO",
                    prefijo,
                    medio_unico(),
                    limite,
                    _telefono(rng),
                    email,
                    _direccion(rng),
                )
            )
            continue

        # responsable inscripto: empresa
        plantilla = rng.choice(
            [
                f"Transporte {rng.choice(APELLIDOS)} SA",
                f"Transportes {rng.choice(ZONAS)} SRL",
                f"Distribuidora {rng.choice(APELLIDOS)} SRL",
                f"Rectificadora {rng.choice(ZONAS)}",
                f"Agropecuaria {rng.choice(ZONAS)} SA",
                f"Casa {rng.choice(APELLIDOS)} Automotores SRL",
                f"Logística {rng.choice(APELLIDOS)} SA",
            ]
        )
        prefijo = rng.choice(["30", "33"])
        limite = rng.choice([1000000, 1500000, 2000000, 3000000, 5000000])
        email = (
            f"compras@{re.sub(r'[^a-z]', '', plantilla.lower())[:12]}.com.ar"
            if rng.random() < 0.7
            else None
        )
        clientes.append(
            (
                codigo,
                plantilla,
                "RESPONSABLE_INSCRIPTO",
                prefijo,
                medio_unico(),
                limite,
                _telefono(rng),
                email,
                _direccion(rng),
            )
        )

    return clientes


# --------------------------------------------------------------------------- vehículos
# Parque real del mercado argentino. (marca, modelo) ÚNICO: la aplicación referencia por ahí.
# (marca, modelo, anio_desde, anio_hasta, motor, version)
VEHICULOS = [
    ("Volkswagen", "Gol Trend", 2013, 2019, "1.6 MSI", "Comfortline"),
    ("Volkswagen", "Gol Power", 2009, 2013, "1.6 Nafta", "Base"),
    ("Volkswagen", "Suran", 2010, 2019, "1.6 Nafta", "Highline"),
    ("Volkswagen", "Amarok", 2011, 2022, "2.0 TDI", "Highline"),
    ("Volkswagen", "Vento", 2011, 2018, "2.5 Nafta", "Luxury"),
    ("Volkswagen", "Polo", 2018, 2024, "1.6 MSI", "Comfortline"),
    ("Volkswagen", "Saveiro", 2010, 2021, "1.6 Nafta", "Cabina Doble"),
    ("Volkswagen", "Fox", 2010, 2018, "1.6 Nafta", "Trendline"),
    ("Toyota", "Hilux", 2016, 2023, "2.8 TDI", "SRV"),
    ("Toyota", "Etios", 2013, 2021, "1.5 Nafta", "XLS"),
    ("Toyota", "Corolla", 2014, 2019, "1.8 Nafta", "XEI"),
    ("Toyota", "Yaris", 2018, 2024, "1.5 Nafta", "XS"),
    ("Toyota", "SW4", 2016, 2023, "2.8 TDI", "SRX"),
    ("Chevrolet", "Corsa Classic", 2009, 2016, "1.4 Nafta", "LS"),
    ("Chevrolet", "Onix", 2016, 2023, "1.4 Nafta", "LT"),
    ("Chevrolet", "Prisma", 2013, 2019, "1.4 Nafta", "LT"),
    ("Chevrolet", "Cruze", 2016, 2023, "1.4 Turbo", "LT"),
    ("Chevrolet", "S10", 2012, 2022, "2.8 TDI", "LTZ"),
    ("Chevrolet", "Agile", 2009, 2016, "1.4 Nafta", "LT"),
    ("Chevrolet", "Spin", 2013, 2020, "1.8 Nafta", "LTZ"),
    ("Chevrolet", "Tracker", 2013, 2020, "1.8 Nafta", "LTZ"),
    ("Ford", "Ka", 2015, 2021, "1.5 Nafta", "SE"),
    ("Ford", "Fiesta", 2011, 2019, "1.6 Nafta", "Titanium"),
    ("Ford", "Focus", 2013, 2019, "2.0 Nafta", "SE"),
    ("Ford", "Ranger", 2013, 2022, "3.2 TDI", "XLT"),
    ("Ford", "EcoSport", 2013, 2021, "1.6 Nafta", "SE"),
    ("Ford", "Territory", 2021, 2024, "1.5 Turbo", "Titanium"),
    ("Fiat", "Palio", 2012, 2017, "1.4 Nafta", "Attractive"),
    ("Fiat", "Siena", 2010, 2016, "1.4 Nafta", "EL"),
    ("Fiat", "Cronos", 2018, 2024, "1.3 Nafta", "Drive"),
    ("Fiat", "Argo", 2018, 2024, "1.3 Nafta", "Drive"),
    ("Fiat", "Uno", 2011, 2020, "1.4 Nafta", "Way"),
    ("Fiat", "Toro", 2016, 2023, "2.0 TDI", "Freedom"),
    ("Fiat", "Strada", 2014, 2020, "1.4 Nafta", "Working"),
    ("Fiat", "Mobi", 2017, 2023, "1.0 Nafta", "Easy"),
    ("Renault", "Clio", 2012, 2016, "1.2 Nafta", "Mío"),
    ("Renault", "Kangoo", 2010, 2018, "1.6 Nafta", "Confort"),
    ("Renault", "Sandero", 2015, 2022, "1.6 Nafta", "Privilege"),
    ("Renault", "Logan", 2014, 2021, "1.6 Nafta", "Privilege"),
    ("Renault", "Duster", 2012, 2022, "1.6 Nafta", "Dynamique"),
    ("Renault", "Stepway", 2016, 2023, "1.6 Nafta", "Dynamique"),
    ("Renault", "Master", 2015, 2023, "2.3 TDI", "L2H2"),
    ("Renault", "Oroch", 2018, 2023, "1.6 Nafta", "Outsider"),
    ("Peugeot", "206", 2009, 2013, "1.4 Nafta", "XR"),
    ("Peugeot", "207 Compact", 2011, 2016, "1.4 Nafta", "Allure"),
    ("Peugeot", "208", 2013, 2020, "1.6 Nafta", "Allure"),
    ("Peugeot", "308", 2013, 2020, "1.6 Nafta", "Allure"),
    ("Peugeot", "Partner", 2012, 2020, "1.6 HDI", "Confort"),
    ("Peugeot", "2008", 2016, 2023, "1.6 Nafta", "Allure"),
    ("Citroën", "C3", 2012, 2020, "1.6 Nafta", "Feel"),
    ("Citroën", "Berlingo", 2012, 2020, "1.6 HDI", "Multispace"),
    ("Citroën", "C4 Lounge", 2014, 2020, "1.6 Turbo", "Feel"),
    ("Nissan", "Frontier", 2016, 2023, "2.3 TDI", "XE"),
    ("Nissan", "Versa", 2015, 2022, "1.6 Nafta", "Sense"),
    ("Nissan", "March", 2014, 2021, "1.6 Nafta", "Sense"),
    ("Nissan", "Kicks", 2017, 2023, "1.6 Nafta", "Sense"),
]

# --------------------------------------------------------------------------- aplicaciones HÉROES
# Compatibilidad CURADA a mano para los héroes. origen: manual (validado) | extraido_ia
# (sugerencia). Regla del dominio: extraido_ia SIEMPRE entra sin confirmar.
# (articulo_codigo, marca, modelo, origen, confirmado, nota)
HERO_APLICACIONES = [
    ("W719/80", "Volkswagen", "Gol Trend", "manual", True, "OEM 030115561AN"),
    (
        "W719/80",
        "Volkswagen",
        "Amarok",
        "extraido_ia",
        False,
        "Sugerido por catálogo, verificar rosca",
    ),
    ("C25114", "Volkswagen", "Gol Trend", "manual", True, None),
    ("CU2545", "Volkswagen", "Gol Trend", "manual", True, None),
    ("WK814/1", "Toyota", "Hilux", "manual", True, "Diesel 2.8"),
    ("W719/80", "Toyota", "Etios", "extraido_ia", False, None),
    ("BKR6E", "Toyota", "Etios", "manual", True, None),
    ("BKR6E", "Chevrolet", "Corsa Classic", "manual", True, None),
    ("FR7DC", "Volkswagen", "Gol Trend", "extraido_ia", False, "Alternativa a bujía original"),
    ("FDB1617", "Volkswagen", "Gol Trend", "manual", True, "Freno delantero"),
    ("FDB1617", "Chevrolet", "Onix", "extraido_ia", False, None),
    ("N1055", "Fiat", "Cronos", "manual", True, None),
    ("G16789", "Volkswagen", "Gol Trend", "manual", True, None),
    ("30125", "Volkswagen", "Gol Trend", "manual", True, "Eje trasero"),
    ("KYB334", "Ford", "Ka", "extraido_ia", False, None),
    ("5PK1123", "Chevrolet", "Corsa Classic", "manual", True, None),
    ("94048", "Ford", "Ranger", "manual", True, "Kit completo con tensor"),
    ("ELAION-F30", "Volkswagen", "Gol Trend", "manual", True, "Servicio 10.000 km"),
    ("ELAION-F30", "Fiat", "Cronos", "extraido_ia", False, None),
    (
        "6204-2RS",
        "Renault",
        "Kangoo",
        "extraido_ia",
        False,
        "Rodamiento genérico, confirmar medida",
    ),
    ("VKBA3550", "Peugeot", "208", "manual", True, None),
    ("H4-12V", "Chevrolet", "Corsa Classic", "manual", True, None),
    ("H7-12V", "Volkswagen", "Gol Trend", "manual", True, "Luz baja"),
    ("H7-12V", "Renault", "Clio", "extraido_ia", False, None),
]

# Rubros cuya compatibilidad con vehículo tiene sentido mostrar (un aceite o una batería aplican
# a casi todo; un filtro o una pastilla son específicos y es donde el buscador de aplicación luce).
RUBROS_CON_APLICACION = {
    "FILTROS",
    "FRENOS",
    "SUSPENSION",
    "ENCENDIDO",
    "CORREAS",
    "EMBRAGUE",
    "DIRECCION",
    "REFRIGERACION",
    "TRANSMISION",
    "RODAMIENTOS",
}


def generar_aplicaciones(articulos: list[tuple]) -> list[tuple]:
    """Héroes + aplicaciones plausibles para un subconjunto de artículos generados.

    No pretende exactitud de fitment (es data de demo): busca VOLUMEN y la mezcla
    manual/extraido_ia que hace visible el diferencial. La IA nunca auto-confirma.
    """
    aplicaciones = list(HERO_APLICACIONES)
    hero_codigos = {a[0] for a in HERO_ARTICULOS}
    vistos = {(a[0], a[1], a[2]) for a in aplicaciones}

    for codigo, _detalle, _costo, _iva, _punto, _marca, rubro, _barra in articulos:
        if codigo in hero_codigos or rubro not in RUBROS_CON_APLICACION:
            continue
        if rng.random() > 0.35:  # solo una parte lleva compatibilidad cargada
            continue
        for _ in range(rng.randint(1, 3)):
            veh = rng.choice(VEHICULOS)
            clave = (codigo, veh[0], veh[1])
            if clave in vistos:
                continue
            vistos.add(clave)
            if rng.random() < 0.6:
                aplicaciones.append((codigo, veh[0], veh[1], "manual", True, None))
            else:
                aplicaciones.append((codigo, veh[0], veh[1], "extraido_ia", False, None))

    return aplicaciones


# --------------------------------------------------------------------------- stock inicial
# Cantidades por artículo. Algunos DEBAJO del punto de pedido a propósito, para que la
# reposición inteligente (Fase 1) tenga algo que alertar desde el primer día.
# articulo_codigo -> (cantidad_central, cantidad_mostrador)
HERO_STOCK = {
    "W719/80": (24, 4),
    "PH5566": (3, 1),
    "C25114": (12, 2),
    "WK814/1": (1, 0),
    "CU2545": (8, 2),
    "5PK1123": (6, 1),
    "94048": (2, 0),
    "BKR6E": (48, 12),
    "FR7DC": (30, 8),
    "FDB1617": (6, 2),
    "N1055": (2, 1),
    "G16789": (4, 0),
    "30125": (3, 0),
    "ELAION-F30": (18, 6),
    "HELIX-HX7": (10, 4),
    "6204-2RS": (5, 3),
    "VKBA3550": (2, 0),
    "H4-12V": (60, 20),
    "H7-12V": (40, 16),
    "KYB334": (1, 0),
}


def generar_stock(articulos: list[tuple]) -> dict[str, tuple[int, int]]:
    """Héroes con su stock curado + generado. ~15% queda bajo el punto de pedido (alertas)."""
    stock: dict[str, tuple[int, int]] = dict(HERO_STOCK)
    for codigo, _detalle, _costo, _iva, punto, _marca, _rubro, _barra in articulos:
        if codigo in stock:
            continue
        punto = int(punto)
        if rng.random() < 0.15:  # bajo el punto de pedido → dispara reposición
            central = rng.randint(0, max(0, punto - 1))
        else:
            central = punto + rng.randint(1, punto * 3)
        mostrador = rng.randint(0, max(1, central // 4)) if rng.random() < 0.6 else 0
        stock[codigo] = (central, mostrador)
    return stock


# --------------------------------------------------------------------------- construcción (orden fijo)
# El orden importa: el azar con semilla es determinista SOLO si se consume siempre igual.
ARTICULOS = generar_articulos()
CLIENTES = generar_clientes()
APLICACIONES = generar_aplicaciones(ARTICULOS)
STOCK = generar_stock(ARTICULOS)


def _escribir(nombre: str, columnas: list[str], filas: list[dict]) -> None:
    DESTINO.mkdir(parents=True, exist_ok=True)
    ruta = DESTINO / nombre
    with ruta.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=columnas)
        writer.writeheader()
        for fila in filas:
            writer.writerow({c: ("" if fila.get(c) is None else fila[c]) for c in columnas})
    print(f"  {nombre:<28} {len(filas):>5} filas")


def generar() -> None:
    print(f"Generando seed en {DESTINO}/")

    _escribir(
        "listas_precio.csv", ["codigo", "nombre"], [{"codigo": c, "nombre": n} for c, n in LISTAS]
    )

    _escribir(
        "depositos.csv", ["codigo", "nombre"], [{"codigo": c, "nombre": n} for c, n in DEPOSITOS]
    )

    _escribir(
        "articulos.csv",
        [
            "codigo",
            "detalle",
            "costo",
            "alicuota_iva",
            "punto_pedido",
            "marca",
            "rubro",
            "codigo_barra",
        ],
        [
            {
                "codigo": a[0],
                "detalle": a[1],
                "costo": a[2],
                "alicuota_iva": a[3],
                "punto_pedido": a[4],
                "marca": a[5],
                "rubro": a[6],
                "codigo_barra": a[7],
            }
            for a in ARTICULOS
        ],
    )

    # Precios: mostrador y mayorista para todos; taller solo para lo que un taller compra.
    precios = []
    for i, a in enumerate(ARTICULOS):
        codigo, costo, rubro = a[0], Decimal(a[2]), a[6]
        listas = ["MOST", "MAY"] + (["TALL"] if rubro in RUBROS_TALLER else [])
        for lista in listas:
            margen = MARGEN_LISTA[lista]
            # La lista mayorista es la competitiva: markup variable por artículo (8%..47%), como en la
            # realidad los ítems que pelean precio. Algunos quedan finos → el guardián de márgenes los marca.
            if lista == "MAY":
                margen = Decimal(8 + (i * 37) % 40)
            precio = _redondear(costo * (1 + margen / 100))
            precios.append(
                {
                    "articulo_codigo": codigo,
                    "lista_codigo": lista,
                    "precio": precio,
                    "margen": margen,
                }
            )
    _escribir(
        "articulo_precios.csv", ["articulo_codigo", "lista_codigo", "precio", "margen"], precios
    )

    _escribir(
        "proveedores.csv",
        ["codigo", "razon_social", "cuit", "telefono", "email"],
        [
            {
                "codigo": p[0],
                "razon_social": p[1],
                "cuit": cuit(p[2], p[3]),
                "telefono": p[4],
                "email": p[5],
            }
            for p in PROVEEDORES
        ],
    )

    # Vínculo artículo-proveedor según el rubro. El costo del proveedor ~5% menor al de lista.
    art_prov = []
    for a in ARTICULOS:
        codigo, costo, rubro = a[0], Decimal(a[2]), a[6]
        for idx, prov in enumerate(RUBRO_PROVEEDORES.get(rubro, [])):
            art_prov.append(
                {
                    "articulo_codigo": codigo,
                    "proveedor_codigo": prov,
                    "codigo_proveedor": f"{prov}-{codigo}",
                    "costo": _redondear(costo * Decimal("0.95")),
                    "es_preferido": "1" if idx == 0 else "0",
                }
            )
    _escribir(
        "articulo_proveedores.csv",
        ["articulo_codigo", "proveedor_codigo", "codigo_proveedor", "costo", "es_preferido"],
        art_prov,
    )

    _escribir(
        "clientes.csv",
        [
            "codigo",
            "denominacion",
            "cuit",
            "cond_fiscal",
            "limite_cta_cte",
            "telefono",
            "email",
            "direccion",
        ],
        [
            {
                "codigo": c[0],
                "denominacion": c[1],
                "cuit": cuit(c[3], c[4]) if c[3] else None,
                "cond_fiscal": c[2],
                "limite_cta_cte": c[5],
                "telefono": c[6],
                "email": c[7],
                "direccion": c[8],
            }
            for c in CLIENTES
        ],
    )

    _escribir(
        "vehiculos.csv",
        ["marca", "modelo", "anio_desde", "anio_hasta", "motor", "version"],
        [
            {
                "marca": v[0],
                "modelo": v[1],
                "anio_desde": v[2],
                "anio_hasta": v[3],
                "motor": v[4],
                "version": v[5],
            }
            for v in VEHICULOS
        ],
    )

    # La aplicación referencia al vehículo por (marca, modelo, anio_desde, anio_hasta):
    # la misma clave con la que el loader arma su índice. Se completan desde VEHICULOS.
    veh_por_nombre = {(v[0], v[1]): (v[2], v[3]) for v in VEHICULOS}
    aplicaciones = []
    for art, marca, modelo, origen, confirmado, nota in APLICACIONES:
        desde, hasta = veh_por_nombre[(marca, modelo)]
        aplicaciones.append(
            {
                "articulo_codigo": art,
                "vehiculo_marca": marca,
                "vehiculo_modelo": modelo,
                "vehiculo_anio_desde": desde,
                "vehiculo_anio_hasta": hasta,
                "origen": origen,
                "confirmado": "1" if confirmado else "0",
                "nota": nota,
            }
        )
    _escribir(
        "articulo_aplicaciones.csv",
        [
            "articulo_codigo",
            "vehiculo_marca",
            "vehiculo_modelo",
            "vehiculo_anio_desde",
            "vehiculo_anio_hasta",
            "origen",
            "confirmado",
            "nota",
        ],
        aplicaciones,
    )

    stock = []
    for codigo, (central, mostrador) in STOCK.items():
        if central:
            stock.append({"articulo_codigo": codigo, "deposito_codigo": "CEN", "cantidad": central})
        if mostrador:
            stock.append(
                {"articulo_codigo": codigo, "deposito_codigo": "MOS", "cantidad": mostrador}
            )
    _escribir("stock_inicial.csv", ["articulo_codigo", "deposito_codigo", "cantidad"], stock)

    print("Listo.")


if __name__ == "__main__":
    generar()
