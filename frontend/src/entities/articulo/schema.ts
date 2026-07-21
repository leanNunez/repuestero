import { z } from "zod";

/** Espeja `ArticuloLeer` del backend. Los campos Decimal llegan como string → se coercionan. */
export const articuloSchema = z.object({
  id: z.number(),
  codigo: z.string(),
  detalle: z.string(),
  costo: z.coerce.number(),
  alicuota_iva: z.coerce.number(),
  punto_pedido: z.coerce.number(),
  marca: z.string().nullable(),
  rubro: z.string().nullable(),
  activo: z.boolean(),
});

/** Item de listado/búsqueda: `score` solo viene en /catalogo/buscar (búsqueda híbrida). */
export const articuloItemSchema = articuloSchema.extend({ score: z.number().optional() });

export const articuloListaSchema = z.array(articuloItemSchema);

/** Espeja `ArticuloPagina` del backend: una página + el total del resultado filtrado. */
export const articuloPaginaSchema = z.object({
  items: articuloListaSchema,
  total: z.number(),
});

/** Opciones de filtro (rubros, marcas): `/catalogo/rubros` y `/catalogo/marcas` → list[str]. */
export const opcionesSchema = z.array(z.string());

export type Articulo = z.infer<typeof articuloSchema>;
export type ArticuloItem = z.infer<typeof articuloItemSchema>;
export type ArticuloPagina = z.infer<typeof articuloPaginaSchema>;
