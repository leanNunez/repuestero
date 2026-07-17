import { z } from "zod";

/** Espeja `ClienteLeer` del backend. `limite_cta_cte` llega como string Decimal → se coerciona. */
export const clienteSchema = z.object({
  id: z.number(),
  codigo: z.string(),
  denominacion: z.string(),
  cuit: z.string().nullable(),
  cond_fiscal: z.string(),
  limite_cta_cte: z.coerce.number(),
  telefono: z.string().nullable(),
  email: z.string().nullable(),
  direccion: z.string().nullable(),
  activo: z.boolean(),
});

export const clienteListaSchema = z.array(clienteSchema);

export type Cliente = z.infer<typeof clienteSchema>;
