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

/** Espeja `ClientePagina`. El `total` es el del resultado FILTRADO, no el del padrón entero: es lo
 *  que deja saber cuántas páginas hay de lo que se está mirando. */
export const clientePaginaSchema = z.object({
  items: clienteListaSchema,
  total: z.number(),
});

export type Cliente = z.infer<typeof clienteSchema>;
export type ClientePagina = z.infer<typeof clientePaginaSchema>;

/** Payload del alta. Espeja `ClienteCrear` del backend.
 *
 * NO lleva `codigo`: lo genera el servidor (`CLI-000001`).
 *
 * `cond_fiscal` va como enum SOLO acá. En `clienteSchema` (lectura) queda `z.string()` a propósito:
 * un cliente importado de Paradox antes de la 0013 podría traer un valor fuera del vocabulario, y
 * con el enum puesto en la lectura ese único registro haría explotar el parseo del listado ENTERO.
 * La reja va en lo que mandamos, no en lo que recibimos. */
export const clienteCrearSchema = z.object({
  denominacion: z.string().min(1).max(140),
  cuit: z.string().max(13).nullable(),
  cond_fiscal: z.enum(["CONSUMIDOR_FINAL", "MONOTRIBUTO", "RESPONSABLE_INSCRIPTO", "EXENTO"]),
  limite_cta_cte: z.string(),
  telefono: z.string().max(40).nullable(),
  email: z.string().max(120).nullable(),
  direccion: z.string().max(160).nullable(),
});

export type ClienteCrear = z.infer<typeof clienteCrearSchema>;
