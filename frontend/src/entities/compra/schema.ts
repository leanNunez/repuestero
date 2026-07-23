import { z } from "zod";

/** Espeja los contratos de `app/compras/schemas.py`.
 *
 * La plata (costo, neto, iva, total) viaja como STRING de punta a punta, igual que en ventas:
 * nunca pasa por Number en el camino de escritura, para no perder centavos. `pesos()` la formatea
 * solo para mostrar. */

export const renglonCompraSchema = z.object({
  articulo_codigo: z.string(),
  cantidad: z.string(),
  costo_unitario: z.string(), // neto, sin IVA
});

export const compraCrearSchema = z.object({
  proveedor_codigo: z.string(),
  deposito_codigo: z.string(),
  numero_comprobante: z.string(),
  condicion: z.enum(["contado", "cta_cte"]),
  renglones: z.array(renglonCompraSchema),
});

/** Acuse del alta (`CompraResponse`). */
export const compraResponseSchema = z.object({
  compra_id: z.number(),
  proveedor_id: z.number(),
  numero_comprobante: z.string(),
  total: z.string(),
  movimientos: z.number(),
});

/** Una fila del listado de compras (`CompraLeer`). */
export const compraLeerSchema = z.object({
  id: z.number(),
  proveedor_id: z.number(),
  numero_comprobante: z.string(),
  fecha: z.string(),
  condicion: z.string(),
  neto: z.string(),
  iva: z.string(),
  total: z.string(),
});

export const compraPaginaSchema = z.object({
  items: z.array(compraLeerSchema),
  total: z.number(),
});

export type CompraResponse = z.infer<typeof compraResponseSchema>;
export type CompraLeer = z.infer<typeof compraLeerSchema>;
