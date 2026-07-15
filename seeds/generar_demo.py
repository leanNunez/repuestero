"""Genera el seed DEMO realista en seeds/demo/ (CSVs que el importador consume).

No son datos reales de ningún comercio (no los tenemos todavía), pero tienen la FORMA y las
asperezas del dato verdadero de una casa de repuestos argentina: filtros y correas que
existen, autos que existen, precios plausibles 2026 en pesos, CUITs con dígito verificador
válido, y compatibilidad poblada mezclando dato confirmado a mano con sugerencias de IA sin
confirmar (el diferencial del producto, y la razón de ser de las columnas origen/confirmado).

Por qué un generador y no CSVs a mano: la integridad referencial entre los diez archivos
(cada articulo_codigo de precios/stock/aplicaciones tiene que existir en articulos) queda
garantizada por construcción, y los CUITs y precios salen calculados, no tipeados a ojo.

    python seeds/generar_demo.py        # reescribe seeds/demo/*.csv
    python -m app.importador --crear-org "Casa Demo" --source seeds/demo

Los CSVs generados se versionan igual: son el artefacto que consume el importador y espejan
la forma de un export de Paradox (Fase 2).
"""

import csv
from decimal import ROUND_HALF_UP, Decimal
from pathlib import Path

DESTINO = Path(__file__).parent / "demo"

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

# --------------------------------------------------------------------------- artículos
# (codigo, detalle, costo, iva, punto_pedido, marca, rubro, codigo_barra)
ARTICULOS = [
    ("W719/80", "FILTRO DE ACEITE MANN W719/80", 9800, 21, 6, "Mann", "FILTROS", "7791234500011"),
    ("PH5566", "FILTRO DE ACEITE FRAM PH5566", 7200, 21, 8, "Fram", "FILTROS", "7791234500028"),
    ("C25114", "FILTRO DE AIRE MANN C25114", 14500, 21, 4, "Mann", "FILTROS", "7791234500035"),
    ("WK814/1", "FILTRO DE COMBUSTIBLE MANN WK814/1", 18200, 21, 3, "Mann", "FILTROS", "7791234500042"),
    ("CU2545", "FILTRO DE HABITACULO MANN CU2545", 12800, 21, 5, "Mann", "FILTROS", "7791234500059"),
    ("5PK1123", "CORREA POLY-V GATES 5PK1123", 15600, 21, 4, "Gates", "CORREAS", "7791234500066"),
    ("94048", "KIT DISTRIBUCION DAYCO 94048", 89400, 21, 2, "Dayco", "CORREAS", "7791234500073"),
    ("BKR6E", "BUJIA NGK BKR6E", 4200, 21, 24, "NGK", "ENCENDIDO", "7791234500080"),
    ("FR7DC", "BUJIA BOSCH FR7DC+", 4800, 21, 16, "Bosch", "ENCENDIDO", "7791234500097"),
    ("FDB1617", "PASTILLA FRENO DELANT FERODO FDB1617", 32500, 21, 4, "Ferodo", "FRENOS", "7791234500103"),
    ("N1055", "PASTILLA FRENO COBREQ N1055", 24800, 21, 5, "Cobreq", "FRENOS", "7791234500110"),
    ("G16789", "AMORTIGUADOR DELANT MONROE G16789", 68900, 21, 2, "Monroe", "SUSPENSION", "7791234500127"),
    ("30125", "AMORTIGUADOR TRASERO SADAR 30125", 52300, 21, 2, "Sadar", "SUSPENSION", "7791234500134"),
    ("ELAION-F30", "ACEITE YPF ELAION F30 5W30 X4L", 38500, 21, 6, "YPF", "LUBRICANTES", "7791234500141"),
    ("HELIX-HX7", "ACEITE SHELL HELIX HX7 10W40 X4L", 41200, 21, 5, "Shell", "LUBRICANTES", "7791234500158"),
    ("6204-2RS", "RODAMIENTO SKF 6204 2RS", 6800, 21, 12, "SKF", "RODAMIENTOS", "7791234500165"),
    ("VKBA3550", "MAZA RUEDA C/RODAMIENTO SKF VKBA3550", 45600, 21, 3, "SKF", "RODAMIENTOS", "7791234500172"),
    ("H4-12V", "LAMPARA OSRAM H4 12V 60/55W", 3900, 21, 24, "Osram", "ILUMINACION", "7791234500189"),
    ("H7-12V", "LAMPARA PHILIPS H7 12V 55W", 4300, 21, 20, "Philips", "ILUMINACION", "7791234500196"),
    ("KYB334", "ESPIRAL SUSPENSION KYB RA3341", 27800, 21, 3, "KYB", "SUSPENSION", "7791234500202"),
]

# --------------------------------------------------------------------------- proveedores
# (codigo, razon_social, prefijo_cuit, medio_cuit, telefono, email)
PROVEEDORES = [
    ("P01", "Distribuidora Autopartes del Litoral SA", "30", "71044569", "0342-4551200", "ventas@autolitoral.com.ar"),
    ("P02", "Repuestos y Filtros Córdoba SRL", "30", "68522345", "0351-4889077", "pedidos@rfcordoba.com.ar"),
    ("P03", "Importadora Rodamientos del Sur SA", "33", "70912888", "011-47125566", "info@rodasur.com.ar"),
    ("P04", "Lubricantes y Accesorios Rosario SRL", "30", "64111222", "0341-4260880", "ventas@lubrirosario.com.ar"),
]

# Qué proveedor surte cada artículo (articulo_codigo -> [(proveedor, es_preferido)]).
# Filtros y correas los trae Litoral y Córdoba; rodamientos, Rodasur; lubricantes, Rosario.
SURTIDO = {
    "FILTROS": [("P01", True), ("P02", False)],
    "CORREAS": [("P01", True)],
    "ENCENDIDO": [("P02", True)],
    "FRENOS": [("P02", True), ("P01", False)],
    "SUSPENSION": [("P01", True)],
    "LUBRICANTES": [("P04", True)],
    "RODAMIENTOS": [("P03", True)],
    "ILUMINACION": [("P02", True)],
}

# --------------------------------------------------------------------------- clientes
# (codigo, denominacion, cond_fiscal, prefijo_cuit, medio_cuit, limite, telefono, email, direccion)
CLIENTES = [
    ("C001", "Taller Mecánico El Rulo", "MONOTRIBUTO", "20", "28456789", 500000, "0341-155667788", "elrulo@gmail.com", "Av. San Martín 2340, Rosario"),
    ("C002", "Transporte La Veloz SA", "RESPONSABLE_INSCRIPTO", "30", "71233445", 3000000, "0341-4780099", "compras@laveloz.com.ar", "Ruta 9 Km 312, Roldán"),
    ("C003", "Rectificadora San Martín", "RESPONSABLE_INSCRIPTO", "27", "32118844", 1200000, "0341-4551133", "rectisanmartin@hotmail.com", "Mendoza 1870, Rosario"),
    ("C004", "Gomería y Repuestos Norte", "MONOTRIBUTO", "23", "30999111", 400000, "0341-156443322", None, "Av. Alberdi 990, Rosario"),
    ("C005", "García Marcelo", "CONSUMIDOR_FINAL", None, None, 0, "0341-153998877", None, None),
    ("C006", "Consumidor Final", "CONSUMIDOR_FINAL", None, None, 0, None, None, None),
]

# --------------------------------------------------------------------------- vehículos
# (marca, modelo, anio_desde, anio_hasta, motor, version)
VEHICULOS = [
    ("Volkswagen", "Gol Trend", 2013, 2019, "1.6 MSI", "Comfortline"),
    ("Volkswagen", "Amarok", 2011, 2022, "2.0 TDI", "Highline"),
    ("Toyota", "Hilux", 2016, 2023, "2.8 TDI", "SRV"),
    ("Toyota", "Etios", 2013, 2021, "1.5 Nafta", "XLS"),
    ("Chevrolet", "Corsa Classic", 2009, 2016, "1.4 Nafta", "LS"),
    ("Chevrolet", "Onix", 2016, 2023, "1.4 Nafta", "LT"),
    ("Ford", "Ka", 2015, 2021, "1.5 Nafta", "SE"),
    ("Ford", "Ranger", 2013, 2022, "3.2 TDI", "XLT"),
    ("Fiat", "Cronos", 2018, 2024, "1.3 Nafta", "Drive"),
    ("Renault", "Kangoo", 2010, 2018, "1.6 Nafta", "Confort"),
    ("Peugeot", "208", 2013, 2020, "1.6 Nafta", "Allure"),
    ("Renault", "Clio", 2012, 2016, "1.2 Nafta", "Mío"),
]

# --------------------------------------------------------------------------- aplicaciones
# Qué repuesto sirve para qué vehículo. origen: manual (validado a mano) | extraido_ia
# (sugerencia sin confirmar). Regla del dominio: extraido_ia SIEMPRE entra sin confirmar.
# (articulo_codigo, marca, modelo, origen, confirmado, nota)
APLICACIONES = [
    ("W719/80", "Volkswagen", "Gol Trend", "manual", True, "OEM 030115561AN"),
    ("W719/80", "Volkswagen", "Amarok", "extraido_ia", False, "Sugerido por catálogo, verificar rosca"),
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
    ("6204-2RS", "Renault", "Kangoo", "extraido_ia", False, "Rodamiento genérico, confirmar medida"),
    ("VKBA3550", "Peugeot", "208", "manual", True, None),
    ("H4-12V", "Chevrolet", "Corsa Classic", "manual", True, None),
    ("H7-12V", "Volkswagen", "Gol Trend", "manual", True, "Luz baja"),
    ("H7-12V", "Renault", "Clio", "extraido_ia", False, None),
]

# --------------------------------------------------------------------------- stock inicial
# Cantidades por artículo. Algunos DEBAJO del punto de pedido a propósito, para que la
# reposición inteligente (Fase 1) tenga algo que alertar desde el primer día.
# articulo_codigo -> (cantidad_central, cantidad_mostrador)
STOCK = {
    "W719/80": (24, 4), "PH5566": (3, 1), "C25114": (12, 2), "WK814/1": (1, 0),
    "CU2545": (8, 2), "5PK1123": (6, 1), "94048": (2, 0), "BKR6E": (48, 12),
    "FR7DC": (30, 8), "FDB1617": (6, 2), "N1055": (2, 1), "G16789": (4, 0),
    "30125": (3, 0), "ELAION-F30": (18, 6), "HELIX-HX7": (10, 4), "6204-2RS": (5, 3),
    "VKBA3550": (2, 0), "H4-12V": (60, 20), "H7-12V": (40, 16), "KYB334": (1, 0),
}


def _escribir(nombre: str, columnas: list[str], filas: list[dict]) -> None:
    DESTINO.mkdir(parents=True, exist_ok=True)
    ruta = DESTINO / nombre
    with ruta.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=columnas)
        writer.writeheader()
        for fila in filas:
            writer.writerow({c: ("" if fila.get(c) is None else fila[c]) for c in columnas})
    print(f"  {nombre:<28} {len(filas):>4} filas")


def generar() -> None:
    print(f"Generando seed en {DESTINO}/")

    _escribir("listas_precio.csv", ["codigo", "nombre"],
              [{"codigo": c, "nombre": n} for c, n in LISTAS])

    _escribir("depositos.csv", ["codigo", "nombre"],
              [{"codigo": c, "nombre": n} for c, n in DEPOSITOS])

    _escribir(
        "articulos.csv",
        ["codigo", "detalle", "costo", "alicuota_iva", "punto_pedido", "marca", "rubro", "codigo_barra"],
        [
            {"codigo": a[0], "detalle": a[1], "costo": a[2], "alicuota_iva": a[3],
             "punto_pedido": a[4], "marca": a[5], "rubro": a[6], "codigo_barra": a[7]}
            for a in ARTICULOS
        ],
    )

    # Precios: mostrador y mayorista para todos; taller solo para lo que un taller compra
    # (filtros, correas, bujías, frenos, lubricantes).
    rubros_taller = {"FILTROS", "CORREAS", "ENCENDIDO", "FRENOS", "LUBRICANTES"}
    precios = []
    for i, a in enumerate(ARTICULOS):
        codigo, costo, rubro = a[0], Decimal(a[2]), a[6]
        listas = ["MOST", "MAY"] + (["TALL"] if rubro in rubros_taller else [])
        for lista in listas:
            margen = MARGEN_LISTA[lista]
            # La lista mayorista es la competitiva: markup variable por artículo (8%..47%), como en la
            # realidad los ítems que pelean precio. Algunos quedan finos → el guardián de márgenes los marca.
            if lista == "MAY":
                margen = Decimal(8 + (i * 37) % 40)
            precio = _redondear(costo * (1 + margen / 100))
            precios.append({"articulo_codigo": codigo, "lista_codigo": lista,
                            "precio": precio, "margen": margen})
    _escribir("articulo_precios.csv",
              ["articulo_codigo", "lista_codigo", "precio", "margen"], precios)

    _escribir(
        "proveedores.csv",
        ["codigo", "razon_social", "cuit", "telefono", "email"],
        [
            {"codigo": p[0], "razon_social": p[1], "cuit": cuit(p[2], p[3]),
             "telefono": p[4], "email": p[5]}
            for p in PROVEEDORES
        ],
    )

    # Vínculo artículo-proveedor según el rubro. El costo del proveedor ~5% menor al de lista.
    art_prov = []
    for a in ARTICULOS:
        codigo, costo, rubro = a[0], Decimal(a[2]), a[6]
        for prov, preferido in SURTIDO.get(rubro, []):
            art_prov.append({
                "articulo_codigo": codigo,
                "proveedor_codigo": prov,
                "codigo_proveedor": f"{prov}-{codigo}",
                "costo": _redondear(costo * Decimal("0.95")),
                "es_preferido": "1" if preferido else "0",
            })
    _escribir("articulo_proveedores.csv",
              ["articulo_codigo", "proveedor_codigo", "codigo_proveedor", "costo", "es_preferido"],
              art_prov)

    _escribir(
        "clientes.csv",
        ["codigo", "denominacion", "cuit", "cond_fiscal", "limite_cta_cte", "telefono", "email", "direccion"],
        [
            {"codigo": c[0], "denominacion": c[1],
             "cuit": cuit(c[3], c[4]) if c[3] else None, "cond_fiscal": c[2],
             "limite_cta_cte": c[5], "telefono": c[6], "email": c[7], "direccion": c[8]}
            for c in CLIENTES
        ],
    )

    _escribir(
        "vehiculos.csv",
        ["marca", "modelo", "anio_desde", "anio_hasta", "motor", "version"],
        [
            {"marca": v[0], "modelo": v[1], "anio_desde": v[2], "anio_hasta": v[3],
             "motor": v[4], "version": v[5]}
            for v in VEHICULOS
        ],
    )

    # La aplicación referencia al vehículo por (marca, modelo, anio_desde, anio_hasta):
    # la misma clave con la que el loader arma su índice. Se completan desde VEHICULOS.
    veh_por_nombre = {(v[0], v[1]): (v[2], v[3]) for v in VEHICULOS}
    aplicaciones = []
    for art, marca, modelo, origen, confirmado, nota in APLICACIONES:
        desde, hasta = veh_por_nombre[(marca, modelo)]
        aplicaciones.append({
            "articulo_codigo": art,
            "vehiculo_marca": marca, "vehiculo_modelo": modelo,
            "vehiculo_anio_desde": desde, "vehiculo_anio_hasta": hasta,
            "origen": origen, "confirmado": "1" if confirmado else "0", "nota": nota,
        })
    _escribir("articulo_aplicaciones.csv",
              ["articulo_codigo", "vehiculo_marca", "vehiculo_modelo",
               "vehiculo_anio_desde", "vehiculo_anio_hasta", "origen", "confirmado", "nota"],
              aplicaciones)

    stock = []
    for codigo, (central, mostrador) in STOCK.items():
        if central:
            stock.append({"articulo_codigo": codigo, "deposito_codigo": "CEN", "cantidad": central})
        if mostrador:
            stock.append({"articulo_codigo": codigo, "deposito_codigo": "MOS", "cantidad": mostrador})
    _escribir("stock_inicial.csv",
              ["articulo_codigo", "deposito_codigo", "cantidad"], stock)

    print("Listo.")


if __name__ == "__main__":
    generar()
