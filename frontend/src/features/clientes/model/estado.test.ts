import { describe, expect, it } from "vitest";

import { aPayload, cuitAceptable, cuitValido, puedeGuardar, VACIO } from "./estado";

describe("cuitValido", () => {
  it.each([
    ["30-71233445-9", "persona jurídica"],
    ["20-28456789-8", "persona física masculina"],
    ["27-32118844-9", "persona física femenina"],
  ])("acepta %s (%s)", (cuit) => {
    expect(cuitValido(cuit)).toBe(true);
  });

  it("rechaza un dígito verificador equivocado", () => {
    // Mismo CUIT que el primero, con el último dígito cambiado: el formato está bien, la cuenta no.
    expect(cuitValido("30-71233445-1")).toBe(false);
  });

  it.each([
    ["30712334459", "sin guiones"],
    ["30-7123344-9", "un dígito de menos"],
    ["30-71233445", "sin verificador"],
    ["AB-71233445-9", "con letras"],
    ["", "vacío"],
  ])("rechaza %s (%s)", (cuit) => {
    expect(cuitValido(cuit)).toBe(false);
  });

  it("coincide con el backend: es el mismo módulo 11", () => {
    // Este caso es el que usa `tests/test_clientes.py`. Si acá diera distinto, el front bloquearía
    // un CUIT que el backend acepta —o al revés— y el desacuerdo sería invisible.
    expect(cuitValido("30-71233445-9")).toBe(true);
    expect(cuitValido("30-71233445-1")).toBe(false);
  });
});

describe("puedeGuardar", () => {
  it("no deja guardar sin denominación", () => {
    expect(puedeGuardar({ ...VACIO, denominacion: "" })).toBe(false);
    expect(puedeGuardar({ ...VACIO, denominacion: "   " })).toBe(false);
  });

  it("alcanza con la denominación: todo lo demás es opcional", () => {
    expect(puedeGuardar({ ...VACIO, denominacion: "Taller El Rulo" })).toBe(true);
  });

  it("un CUIT vacío es aceptable — el consumidor final no tiene por qué darlo", () => {
    expect(cuitAceptable("")).toBe(true);
    expect(puedeGuardar({ ...VACIO, denominacion: "Mostrador", cuit: "" })).toBe(true);
  });

  it("pero un CUIT escrito a medias bloquea: parece un dato y no lo es", () => {
    expect(puedeGuardar({ ...VACIO, denominacion: "Trucho SA", cuit: "30-71233445-1" })).toBe(false);
  });
});

describe("aPayload", () => {
  it("manda null en los opcionales vacíos, no string vacío", () => {
    const body = aPayload({ ...VACIO, denominacion: "Gomería Norte" });

    expect(body.cuit).toBeNull();
    expect(body.telefono).toBeNull();
    expect(body.email).toBeNull();
    expect(body.direccion).toBeNull();
  });

  it("recorta los espacios de los lados", () => {
    const body = aPayload({ ...VACIO, denominacion: "  Taller El Rulo  ", cuit: " " });

    expect(body.denominacion).toBe("Taller El Rulo");
    expect(body.cuit).toBeNull();
  });

  it("un límite de crédito sin cargar viaja como 0, no como vacío", () => {
    expect(aPayload({ ...VACIO, denominacion: "X" }).limite_cta_cte).toBe("0");
  });

  it("respeta el límite cargado", () => {
    const body = aPayload({ ...VACIO, denominacion: "X", limite_cta_cte: "150000.00" });

    expect(body.limite_cta_cte).toBe("150000.00");
  });

  it("no manda codigo: lo genera el servidor", () => {
    expect(aPayload({ ...VACIO, denominacion: "X" })).not.toHaveProperty("codigo");
  });
});
