import { describe, expect, it } from "vitest";

import { ventaResponseSchema } from "./schema";

/** Respuesta REAL de `POST /ventas`, con los nombres y tipos que arma
 *  `app/ventas/router.py`: la plata como string (Decimal), no como número. */
const EMITIDA = {
  venta_id: 41,
  tipo: "FAC",
  pto_venta: 1,
  numero: 12,
  total: "242.00",
  movimientos: 1,
  advertencias: [
    "Cliente Al Límite quedó debiendo 242.00 y su límite es 100.00: se pasó por 142.00.",
  ],
};

describe("ventaResponseSchema", () => {
  it("deja pasar la advertencia del límite de crédito", () => {
    expect(ventaResponseSchema.parse(EMITIDA).advertencias).toHaveLength(1);
  });

  it("una venta sin problemas trae la lista vacía", () => {
    const r = ventaResponseSchema.parse({ ...EMITIDA, advertencias: [] });

    expect(r.advertencias).toEqual([]);
  });

  it("una respuesta SIN el campo no rompe la pantalla de una venta que sí se emitió", () => {
    // El backend lo manda siempre, pero el default evita que un deploy viejo del backend —o una
    // respuesta cacheada— tire el parseo abajo justo después de facturar. Fallar acá sería
    // esconderle a la persona un comprobante que YA existe.
    const { advertencias: _, ...sinCampo } = EMITIDA;

    expect(ventaResponseSchema.parse(sinCampo).advertencias).toEqual([]);
  });

  it("la plata sigue viajando como string", () => {
    // Si alguien la pasa a `z.coerce.number()`, 242.00 deja de ser exacto y el total que se
    // muestra después de facturar puede no coincidir con el comprobante.
    expect(typeof ventaResponseSchema.parse(EMITIDA).total).toBe("string");
  });
});
