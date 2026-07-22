import { z } from "zod";

/** Espeja los contratos de `app/ventas/schemas.py`.
 *
 * La plata (precio, neto, iva, total) viaja como STRING de punta a punta, igual que en el
 * remito: nunca pasa por Number en el camino de escritura, para no perder centavos al
 * mandarla de vuelta. `pesos()` la formatea solo para mostrar. */

export const renglonVentaSchema = z.object({
  articulo_codigo: z.string(),
  cantidad: z.string(),
  precio_unitario: z.string(), // neto, sin IVA
});

export const ventaCrearSchema = z.object({
  cliente_codigo: z.string(),
  deposito_codigo: z.string(),
  condicion: z.enum(["contado", "cta_cte"]),
  renglones: z.array(renglonVentaSchema),
});

/** Acuse del alta (`VentaResponse`). */
export const ventaResponseSchema = z.object({
  venta_id: z.number(),
  tipo: z.string(),
  pto_venta: z.number(),
  numero: z.number(),
  total: z.string(),
  movimientos: z.number(),
});

/** Precio a precargar en un renglón (`PrecioSugeridoLeer`). `precio` es null si esa lista no
 * tiene precio fijado para el artículo: ahí el operador lo tipea a mano. */
export const precioSugeridoSchema = z.object({
  articulo_codigo: z.string(),
  precio: z.string().nullable(),
  lista_codigo: z.string().nullable(),
});

/** Una fila del listado de ventas (`VentaLeer`). */
export const ventaLeerSchema = z.object({
  id: z.number(),
  cliente_id: z.number(),
  tipo: z.string(),
  pto_venta: z.number(),
  numero: z.number(),
  fecha: z.string(),
  condicion: z.string(),
  neto: z.string(),
  iva: z.string(),
  total: z.string(),
});

export const ventaPaginaSchema = z.object({
  items: z.array(ventaLeerSchema),
  total: z.number(),
});

export type VentaResponse = z.infer<typeof ventaResponseSchema>;
export type PrecioSugerido = z.infer<typeof precioSugeridoSchema>;
export type VentaLeer = z.infer<typeof ventaLeerSchema>;
