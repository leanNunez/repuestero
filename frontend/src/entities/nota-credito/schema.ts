import { z } from "zod";

/** Espeja los contratos de notas de crédito de `app/ventas/schemas.py`.
 *
 * La plata (precio, importes, cantidades) viaja como STRING, igual que en ventas: no pasa por
 * Number en el camino de escritura para no perder centavos. `pesos()` la formatea solo al
 * mostrar. */

/** Lo que resta acreditar de un renglón de una venta (`RenglonAcreditableLeer`). La UI lo usa
 * para precargar el flujo de NC y fijar el máximo de cada renglón. */
export const renglonAcreditableSchema = z.object({
  articulo_id: z.number(),
  articulo_codigo: z.string(),
  descripcion: z.string(),
  precio_unitario: z.string(),
  alicuota_iva: z.string(),
  cantidad_vendida: z.string(),
  cantidad_acreditable: z.string(),
});

export const renglonesAcreditablesSchema = z.array(renglonAcreditableSchema);

/** Acuse del alta de una NC (`NotaCreditoResponse`). */
export const notaCreditoResponseSchema = z.object({
  nota_credito_id: z.number(),
  ref_comprobante_id: z.number(),
  tipo: z.string(),
  pto_venta: z.number(),
  numero: z.number(),
  total: z.string(),
  movimientos: z.number(),
});

export type RenglonAcreditable = z.infer<typeof renglonAcreditableSchema>;
export type NotaCreditoResponse = z.infer<typeof notaCreditoResponseSchema>;
