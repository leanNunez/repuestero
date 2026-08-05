import { describe, expect, it } from "vitest";

import { articuloAltaRequestSchema } from "@/entities/articulo/schema";

import {
  ALICUOTAS_IVA,
  aPayload,
  precioInvalido,
  precioSinLista,
  puedeGuardar,
  VACIO,
} from "./estado";

describe("puedeGuardar", () => {
  const MINIMO = { ...VACIO, codigo: "MAH-OC90", detalle: "Filtro de aceite" };

  it("pide código y detalle: lo demás es opcional", () => {
    expect(puedeGuardar(MINIMO)).toBe(true);
    expect(puedeGuardar({ ...MINIMO, codigo: "" })).toBe(false);
    expect(puedeGuardar({ ...MINIMO, detalle: "" })).toBe(false);
  });

  it("un campo con solo espacios no es un dato", () => {
    // El service hace `.strip()` antes de validar: `"   "` tiene largo 3 y pasaría un min_length
    // de Pydantic, pero el alta lo rechaza. Acá se ve antes de mandarlo.
    expect(puedeGuardar({ ...MINIMO, codigo: "   " })).toBe(false);
    expect(puedeGuardar({ ...MINIMO, detalle: "  " })).toBe(false);
  });

  it("bloquea el precio sin lista — el 422 que el backend devolvería", () => {
    expect(puedeGuardar({ ...MINIMO, precio: "15000" })).toBe(false);
    expect(puedeGuardar({ ...MINIMO, precio: "15000", lista_id: "3" })).toBe(true);
  });

  it("sin precio, la lista no importa", () => {
    // Caso frecuente: se carga el artículo para tenerlo en el catálogo y el precio se pone después.
    expect(puedeGuardar({ ...MINIMO, lista_id: "3" })).toBe(true);
  });
});

describe("precioInvalido", () => {
  const MINIMO = { ...VACIO, codigo: "MAH-OC90", detalle: "Filtro de aceite" };

  it("un precio en cero bloquea: no se descarta en silencio", () => {
    // El backend valida `gt=0`, así que un cero no se puede fijar. Si el payload lo mandara como
    // null, el artículo se crearía "sin precio" y la persona vería una advertencia sobre algo que
    // sí escribió. El botón apagado obliga a decidir: poner un precio, o vaciar el campo.
    expect(precioInvalido({ ...MINIMO, precio: "0" })).toBe(true);
    expect(puedeGuardar({ ...MINIMO, precio: "0", lista_id: "3" })).toBe(false);
  });

  it("el campo vacío no es un precio inválido: es no haber puesto precio", () => {
    expect(precioInvalido(MINIMO)).toBe(false);
    expect(precioInvalido({ ...MINIMO, precio: "   " })).toBe(false);
  });

  it("un precio en cero no exige lista — el problema es el cero, no la lista", () => {
    expect(precioSinLista({ ...MINIMO, precio: "0" })).toBe(false);
  });
});

describe("aPayload", () => {
  const MINIMO = { ...VACIO, codigo: "MAH-OC90", detalle: "Filtro de aceite" };

  it("manda null en los opcionales vacíos, no string vacío", () => {
    const body = aPayload(MINIMO);

    expect(body.marca).toBeNull();
    expect(body.rubro).toBeNull();
    expect(body.codigo_barra).toBeNull();
    expect(body.costo_dolar).toBeNull();
  });

  it("costo y punto de pedido vacíos viajan como 0, no como null", () => {
    // Las columnas son NOT NULL con default 0: un artículo sin costo cargado cuesta cero.
    const body = aPayload(MINIMO);

    expect(body.costo).toBe("0");
    expect(body.punto_pedido).toBe("0");
  });

  it("recorta los espacios de los lados", () => {
    const body = aPayload({ ...MINIMO, codigo: "  MAH-OC90 ", rubro: " Filtros " });

    expect(body.codigo).toBe("MAH-OC90");
    expect(body.rubro).toBe("Filtros");
  });

  it("NO toca el case: la tipografía de la marca es información", () => {
    // "MANN-FILTER" y "Mann-Filter" se escriben distinto a propósito. Un `.toUpperCase()` acá
    // conviviría con todo el catálogo importado de Paradox, que tiene su case original.
    expect(aPayload({ ...MINIMO, marca: "Mann-Filter" }).marca).toBe("Mann-Filter");
  });

  it("la plata viaja como STRING, nunca como número", () => {
    // Un float de JavaScript no representa los decimales exactamente: 12345.67 puede volver
    // como 12345.669999999999. El backend recibe Decimal — se le manda el texto tal cual.
    const body = aPayload({ ...MINIMO, costo: "12345.67", precio: "19999.99", lista_id: "3" });

    expect(body.costo).toBe("12345.67");
    expect(body.precio).toBe("19999.99");
    expect(typeof body.costo).toBe("string");
    expect(typeof body.precio).toBe("string");
  });

  it("la lista viaja como número: es una clave, no un importe", () => {
    expect(aPayload({ ...MINIMO, precio: "15000", lista_id: "3" }).lista_id).toBe(3);
  });

  it("sin precio no manda lista, aunque el selector tenga una elegida", () => {
    // El `<select>` siempre tiene algo puesto. Mandar la lista sin precio sería decir que
    // fijamos un precio que no fijamos.
    const body = aPayload({ ...MINIMO, lista_id: "3" });

    expect(body.precio).toBeNull();
    expect(body.lista_id).toBeNull();
  });

  it("el IVA por defecto es 21, con los dos decimales de la columna", () => {
    expect(aPayload(MINIMO).alicuota_iva).toBe("21.00");
  });

  it("lo que arma pasa el schema del contrato", () => {
    // El payload y el schema se escriben en dos archivos distintos: este test es lo que hace
    // que no se separen sin que nadie se entere.
    const completo = {
      ...MINIMO,
      costo: "1000",
      marca: "Mann-Filter",
      rubro: "Filtros",
      precio: "15000",
      lista_id: "3",
    };

    expect(() => articuloAltaRequestSchema.parse(aPayload(completo))).not.toThrow();
    expect(() => articuloAltaRequestSchema.parse(aPayload(MINIMO))).not.toThrow();
  });
});

describe("ALICUOTAS_IVA", () => {
  it("es el vocabulario cerrado de AFIP: 0, 10.5, 21 y 27", () => {
    expect(ALICUOTAS_IVA.map((a) => a.id).sort()).toEqual(["0.00", "10.50", "21.00", "27.00"]);
  });

  it("ofrece 21 primero: es lo que lleva casi todo un repuesto", () => {
    expect(ALICUOTAS_IVA[0].id).toBe("21.00");
  });

  it("no se separa del enum del contrato", () => {
    // El vocabulario está escrito dos veces: acá con su label, y en el schema como enum. Agregar
    // una alícuota en un solo lado haría que el `<select>` ofrezca algo que el payload rechaza.
    expect(ALICUOTAS_IVA.map((a) => a.id).sort()).toEqual(
      [...articuloAltaRequestSchema.shape.alicuota_iva.options].sort(),
    );
  });
});
