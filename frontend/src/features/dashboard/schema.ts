import { z } from "zod";

export const resumenSchema = z.object({
  total_articulos: z.number(),
  bajo_punto_pedido: z.number(),
  margen_bajo: z.number(),
  valor_stock: z.coerce.number(),
});

export const reposicionItemSchema = z.object({
  codigo: z.string(),
  detalle: z.string(),
  marca: z.string().nullable(),
  stock: z.coerce.number(),
  punto_pedido: z.coerce.number(),
  faltante: z.coerce.number(),
});

export const margenItemSchema = z.object({
  codigo: z.string(),
  detalle: z.string(),
  marca: z.string().nullable(),
  costo: z.coerce.number(),
  precio: z.coerce.number(),
  margen: z.coerce.number(),
  bajo: z.boolean(),
});

export const reposicionSchema = z.array(reposicionItemSchema);
export const margenesSchema = z.array(margenItemSchema);

export type Resumen = z.infer<typeof resumenSchema>;
export type ReposicionItem = z.infer<typeof reposicionItemSchema>;
export type MargenItem = z.infer<typeof margenItemSchema>;
