import { z } from "zod";

/** Espeja los schemas de `app/ingesta_visual/schemas.py`.
 *
 * OJO con la plata: acá NO se coerciona a number, a diferencia de `articulo/schema.ts`.
 * Los importes llegan como string (Pydantic serializa Decimal así) y se MANTIENEN string
 * en todo el round-trip, porque este es el único lugar del front que le devuelve plata al
 * backend para que la escriba. Un float de JavaScript no puede representar 0.1 exacto:
 * pasar por number y volver a string es cómo un costo de 12.500,00 se convierte en
 * 12500.000000000002. Para MOSTRAR se formatea; para GUARDAR viaja tal cual.
 */

export const FLAGS = [
  "sin_codigo",
  "sin_margen",
  "sin_listas",
  "baja_confianza",
  "salto_de_costo",
  "costo_cero",
  "duplicado",
  "texto_sospechoso",
  "alta_sin_precio",
] as const;

export type Flag = (typeof FLAGS)[number];

/** Qué le decimos al humano sobre cada flag. El slug del backend es una clave, no un texto
 * para mostrar: quien atiende el mostrador no sabe qué es "sin_margen". */
export const FLAG_TEXTO: Record<Flag, { label: string; detalle: string }> = {
  sin_codigo: {
    label: "Sin código",
    detalle: "No se leyó el código. Completalo para poder cargarlo.",
  },
  sin_margen: {
    label: "Sin margen",
    detalle: "Este artículo no tiene margen cargado: su precio de venta NO se toca.",
  },
  sin_listas: {
    label: "Sin listas",
    detalle: "El artículo no tiene precios de venta cargados.",
  },
  baja_confianza: {
    label: "Dudoso",
    detalle: "Repu no está seguro de haber leído bien este renglón. Revisalo.",
  },
  salto_de_costo: {
    label: "Salto de costo",
    detalle: "El costo cambió mucho respecto del anterior. Puede ser un error de lectura.",
  },
  costo_cero: { label: "Costo $0", detalle: "El costo leído es cero." },
  duplicado: {
    label: "Repetido",
    detalle: "Este código aparece más de una vez en el remito.",
  },
  texto_sospechoso: {
    label: "Texto raro",
    detalle: "La descripción tiene texto sospechoso. Leelo antes de incluirlo.",
  },
  alta_sin_precio: {
    label: "Artículo nuevo",
    detalle: "Se va a crear sin precio de venta. Poneselo después.",
  },
};

export const precioPreviewSchema = z.object({
  lista_codigo: z.string(),
  lista_nombre: z.string(),
  precio_actual: z.string(),
  margen: z.string().nullable(),
  /** null ⇔ no hay margen cargado ⇒ el precio no se toca. */
  precio_nuevo: z.string().nullable(),
});

export const renglonPropuestaSchema = z.object({
  codigo: z.string().nullable(),
  descripcion: z.string(),
  cantidad: z.string(),
  costo_unitario: z.string(),
  confianza: z.number(),
  accion: z.enum(["alta", "actualizacion"]),
  articulo_id: z.number().nullable(),
  detalle_actual: z.string().nullable(),
  costo_actual: z.string().nullable(),
  precios: z.array(precioPreviewSchema),
  atencion: z.array(z.enum(FLAGS)),
  incluir_sugerido: z.boolean(),
});

export const propuestaSchema = z.object({
  remito_hash: z.string(),
  ya_procesado: z.boolean(),
  procesado_en: z.string().nullable(),
  proveedor_nombre: z.string().nullable(),
  proveedor_cuit: z.string().nullable(),
  numero_remito: z.string().nullable(),
  fecha: z.string().nullable(),
  total_declarado: z.string().nullable(),
  total_calculado: z.string(),
  renglones: z.array(renglonPropuestaSchema),
  advertencias: z.array(z.string()),
});

export const confirmarResponseSchema = z.object({
  remito_id: z.number(),
  articulos_creados: z.array(z.string()),
  articulos_actualizados: z.array(z.string()),
  movimientos: z.number(),
  precios_recalculados: z.number(),
  renglones_sin_margen: z.array(z.string()),
  advertencias: z.array(z.string()),
});

export type PrecioPreview = z.infer<typeof precioPreviewSchema>;
export type RenglonPropuesta = z.infer<typeof renglonPropuestaSchema>;
export type Propuesta = z.infer<typeof propuestaSchema>;
export type ConfirmarResponse = z.infer<typeof confirmarResponseSchema>;
