import { describe, expect, it } from "vitest";

import { margenItemSchema, resumenSchema } from "./schema";

describe("schemas del dashboard", () => {
  it("coerce los Decimal que el backend manda como string", () => {
    const r = resumenSchema.parse({
      total_articulos: 20,
      bajo_punto_pedido: 7,
      margen_bajo: 7,
      valor_stock: "4368700.000000",
    });
    expect(r.valor_stock).toBe(4368700);

    const m = margenItemSchema.parse({
      codigo: "X",
      detalle: "d",
      marca: null,
      costo: "100.0",
      precio: "105.0",
      margen: "4.76",
      bajo: true,
    });
    expect(m.costo).toBe(100);
    expect(m.margen).toBeCloseTo(4.76);
  });

  it("rechaza un payload que no valida", () => {
    expect(() => resumenSchema.parse({ total_articulos: "no-numero" })).toThrow();
  });
});
