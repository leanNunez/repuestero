import { z } from "zod";

/** Espeja `ProveedorLeer` del backend. */
export const proveedorSchema = z.object({
  id: z.number(),
  codigo: z.string(),
  razon_social: z.string(),
  cuit: z.string().nullable(),
  telefono: z.string().nullable(),
  email: z.string().nullable(),
  activo: z.boolean(),
});

export const proveedorListaSchema = z.array(proveedorSchema);

/** Espeja `ProveedorPagina`. El `total` es el del resultado FILTRADO, no el del padrón entero. */
export const proveedorPaginaSchema = z.object({
  items: proveedorListaSchema,
  total: z.number(),
});

export type Proveedor = z.infer<typeof proveedorSchema>;
export type ProveedorPagina = z.infer<typeof proveedorPaginaSchema>;

/** Payload del alta. Espeja `ProveedorCrear` del backend.
 *
 * NO lleva `codigo`: lo genera el servidor (`PRV-000001`).
 *
 * Sin `cond_fiscal` ni `limite_cta_cte`, a diferencia del cliente: a un proveedor no se le factura
 * ni se le fija un límite de crédito. */
export const proveedorCrearSchema = z.object({
  razon_social: z.string().min(1).max(120),
  cuit: z.string().max(13).nullable(),
  telefono: z.string().max(40).nullable(),
  email: z.string().max(120).nullable(),
});

export type ProveedorCrear = z.infer<typeof proveedorCrearSchema>;
