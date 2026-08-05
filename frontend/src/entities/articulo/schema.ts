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

/** Espeja `ListaPrecioLeer`. El `id` es lo que viaja en el alta (`upsert_precio` toma ids); el
 *  `codigo` se muestra al lado del nombre, no identifica. */
export const listaPrecioSchema = z.object({
  id: z.number(),
  codigo: z.string(),
  nombre: z.string(),
});

export const listaPrecioListaSchema = z.array(listaPrecioSchema);

/** Payload del alta. Espeja `ArticuloAltaRequest` del backend, que hereda de `ArticuloCrear` y le
 *  suma la intención de fijar un precio.
 *
 * El nombre sigue al del backend y NO es `articuloCrearSchema`: allá `ArticuloCrear` es otra
 * cosa —el artículo pelado, sin precio ni lista, el que usan el importador y la ingesta—. Dos
 * shapes distintos con el mismo nombre es exactamente el malentendido que cuesta una tarde.
 *
 * La plata viaja como STRING, nunca como número: el backend recibe `Decimal` y un float de
 * JavaScript no representa `0.1` exactamente. `12345.67` ida y vuelta por un `number` puede
 * llegar como `12345.669999999999`. Los largos máximos espejan los `Field(max_length=...)` del
 * backend: son la misma reja puesta antes del viaje, no una validación distinta.
 *
 * `alicuota_iva` va como enum SOLO acá, igual que `cond_fiscal` en `clienteCrearSchema`: la reja
 * va en lo que mandamos, no en lo que recibimos. El backend valida un RANGO (0 a 100), así que
 * cerrar el vocabulario es una decisión del front; en `articuloSchema` (lectura) queda numérico
 * porque un artículo importado de Paradox puede traer cualquier alícuota, y con el enum puesto en
 * la lectura ese único registro haría explotar el parseo del listado entero.
 *
 * `lista_id` sí es número: es una clave, no un importe. */
export const articuloAltaRequestSchema = z.object({
  codigo: z.string().min(1).max(40),
  detalle: z.string().min(1).max(200),
  costo: z.string(),
  costo_dolar: z.string().nullable(),
  alicuota_iva: z.enum(["0.00", "10.50", "21.00", "27.00"]),
  punto_pedido: z.string(),
  codigo_barra: z.string().nullable(),
  marca: z.string().nullable(),
  rubro: z.string().nullable(),
  precio: z.string().nullable(),
  lista_id: z.number().nullable(),
});

/** Espeja `ArticuloAltaResponse`: el artículo creado + los avisos no bloqueantes.
 *
 * Anidado y no plano, igual que el backend: `advertencias` no es un campo del artículo (una fila
 * del listado no tiene advertencias), es el resultado de ESTA alta. */
export const articuloAltaResponseSchema = z.object({
  articulo: articuloSchema,
  advertencias: z.array(z.string()),
});

export type Articulo = z.infer<typeof articuloSchema>;
export type ArticuloItem = z.infer<typeof articuloItemSchema>;
export type ArticuloPagina = z.infer<typeof articuloPaginaSchema>;
export type ListaPrecio = z.infer<typeof listaPrecioSchema>;
export type ArticuloAltaRequest = z.infer<typeof articuloAltaRequestSchema>;
export type ArticuloAltaResponse = z.infer<typeof articuloAltaResponseSchema>;
