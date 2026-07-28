import { describe, expect, it } from "vitest";

import { aPayload, PAGE_SIZE, puedeGuardar, queryPadron, VACIO } from "./estado";

describe("queryPadron", () => {
  it("fija el tamaño de página del padrón de proveedores", () => {
    expect(queryPadron("", 1)).toBe(`limite=${PAGE_SIZE}&offset=0`);
  });

  it("manda la búsqueda cuando hay texto", () => {
    expect(queryPadron("bulonera", 1)).toContain("buscar=bulonera");
  });
});

describe("puedeGuardar", () => {
  it("con el formulario vacío no deja guardar", () => {
    expect(puedeGuardar(VACIO)).toBe(false);
  });

  it("con la razón social sola alcanza", () => {
    // A un proveedor nuevo muchas veces se lo carga con el nombre del remito y nada más.
    expect(puedeGuardar({ ...VACIO, razon_social: "Distribuidora Sur" })).toBe(true);
  });

  it("una razón social de puros espacios no alcanza", () => {
    expect(puedeGuardar({ ...VACIO, razon_social: "   " })).toBe(false);
  });

  it("un CUIT escrito a medias bloquea el alta", () => {
    // El CUIT es opcional, pero si lo escribió tiene que estar bien: uno a medias parece un dato.
    expect(
      puedeGuardar({ ...VACIO, razon_social: "Distribuidora Sur", cuit: "30-71233445-1" }),
    ).toBe(false);
  });

  it("un CUIT válido deja guardar", () => {
    expect(
      puedeGuardar({ ...VACIO, razon_social: "Distribuidora Sur", cuit: "30-71233445-9" }),
    ).toBe(true);
  });
});

describe("aPayload", () => {
  it("los opcionales vacíos viajan como null, no como string vacío", () => {
    // La columna es nullable: un "" es un dato que después hay que salir a limpiar.
    const payload = aPayload({ ...VACIO, razon_social: "Distribuidora Sur" });

    expect(payload).toEqual({
      razon_social: "Distribuidora Sur",
      cuit: null,
      telefono: null,
      email: null,
    });
  });

  it("recorta los espacios de sobra", () => {
    const payload = aPayload({
      razon_social: "  Distribuidora Sur  ",
      cuit: " 30-71233445-9 ",
      telefono: "  0341-4567890  ",
      email: " ventas@sur.com ",
    });

    expect(payload.razon_social).toBe("Distribuidora Sur");
    expect(payload.cuit).toBe("30-71233445-9");
    expect(payload.telefono).toBe("0341-4567890");
    expect(payload.email).toBe("ventas@sur.com");
  });

  it("NO manda código: lo asigna el servidor", () => {
    expect(aPayload({ ...VACIO, razon_social: "Distribuidora Sur" })).not.toHaveProperty("codigo");
  });
});
