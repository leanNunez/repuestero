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

export type Proveedor = z.infer<typeof proveedorSchema>;
