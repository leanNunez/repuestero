import { z } from "zod";

/** Espeja los contratos de `app/caja/schemas.py`.
 *
 * La plata viaja como STRING de punta a punta, igual que en cuenta corriente, ventas y compras:
 * nunca pasa por `Number` en el camino de escritura, para no perder centavos. `pesos()` la formatea
 * solo para mostrar.
 *
 * Movimiento y cheque llevan schemas SEPARADOS aunque los dos vengan de `/caja`: son contratos
 * distintos. Unificarlos es el error que ya se pagó una vez con `imputacionResponseSchema` y
 * `ajusteResponseSchema` (ver `entities/cuenta-corriente/schema.ts`), donde declarar una clave
 * requerida en el schema compartido rompió la respuesta que no la traía. */

/** Un renglón del libro de caja (`MovimientoCajaLeer`). */
export const movimientoCajaSchema = z.object({
  id: z.number(),
  fecha: z.string(),
  concepto: z.string(),
  forma: z.string(),
  ingreso: z.string(),
  egreso: z.string(),
  detalle: z.string().nullable(),
  /** NULL = lo cargó una persona. Cargados = lo emitió un documento (un recibo, un cheque). */
  ref_tipo: z.string().nullable(),
  ref_id: z.number().nullable(),
  /** Cuándo se REGISTRÓ, contra `fecha`, que es cuándo se movió la plata. */
  creado_en: z.string(),
  /** Cuánto había de ESTA forma después de este movimiento. Lo calcula el SQL con una window
   *  function sobre todo el libro; el front solo tiene una página y no puede recalcularlo. */
  saldo_acumulado: z.string(),
});

export const movimientoCajaPaginaSchema = z.object({
  items: z.array(movimientoCajaSchema),
  total: z.number(),
});

/** El saldo discriminado por forma, más los dos números que la pantalla muestra grandes.
 *
 * `cheques_en_cartera` es DISTINTO de `por_forma.cheque` y por eso viaja aparte: aquel es el neto
 * de los cheques recibidos menos los emitidos —un cheque propio escribe un egreso sin
 * contrapartida, porque no entra a la cartera sino que sale del bolsillo— así que se va a negativo
 * sin que nada esté mal. El valor de la cartera sale de la tabla `cheques`, y es el que se muestra. */
export const saldoCajaSchema = z.object({
  efectivo: z.string(),
  por_forma: z.record(z.string(), z.string()),
  cheques_en_cartera: z.string(),
});

/** Acuse de un alta manual. `advertencias` es la regla "advertir, no bloquear": si el movimiento
 *  dejó la caja en negativo, la operación se ACEPTA igual y el aviso viene acá. Mismo nombre de
 *  clave que en ingesta visual y en el pago a proveedor. */
export const movimientoCajaResponseSchema = z.object({
  movimiento_id: z.number(),
  concepto: z.string(),
  forma: z.string(),
  saldo: z.string(),
  advertencias: z.array(z.string()),
});

/** Un cheque de la cartera (`ChequeLeer`).
 *
 * `banco`, `numero` y las fechas son nullable porque al derivar el cheque desde un recibo todavía
 * no se conocen: un renglón de forma de pago solo trae forma y monto. */
export const chequeSchema = z.object({
  id: z.number(),
  /** 'recibido' (me lo dio un cliente) | 'emitido' (lo firmé yo). */
  origen: z.string(),
  importe: z.string(),
  estado: z.string(),
  banco: z.string().nullable(),
  numero: z.string().nullable(),
  fecha_emision: z.string().nullable(),
  fecha_cobro: z.string().nullable(),
  conciliado: z.boolean(),
  fecha_conciliacion: z.string().nullable(),
  ref_tipo: z.string().nullable(),
  ref_id: z.number().nullable(),
  creado_en: z.string(),
});

export const chequePaginaSchema = z.object({
  items: z.array(chequeSchema),
  total: z.number(),
  /** Valor de los cheques todavía en cartera, del TOTAL de la org y no de la página: una suma que
   *  dependiera de la paginación no serviría para arquear. */
  valor_en_cartera: z.string(),
});

/** Acuse de una transición: el papel como quedó y la plata que movió.
 *
 * Los movimientos vienen del mismo `MovimientoCajaResponse` que el alta manual, así que traen
 * también un `advertencias` que acá NO se declara — Zod lo descarta, y es a propósito: una
 * transición **no puede** dejar la caja en negativo. Cobrar suma, y rechazar y entregar sacan de la
 * cartera exactamente lo que un ingreso previo puso. Declararlo sería pedirle a la pantalla que
 * maneje un caso que el dominio no permite. */
export const chequeResponseSchema = z.object({
  cheque: chequeSchema,
  /** Vacío si la transición no movió plata (depositar, o cualquier transición de un emitido). */
  movimientos: z.array(
    z.object({
      movimiento_id: z.number(),
      concepto: z.string(),
      forma: z.string(),
      saldo: z.string(),
    }),
  ),
  saldos: z.record(z.string(), z.string()),
});

export type MovimientoCaja = z.infer<typeof movimientoCajaSchema>;
export type MovimientoCajaPagina = z.infer<typeof movimientoCajaPaginaSchema>;
export type SaldoCaja = z.infer<typeof saldoCajaSchema>;
export type MovimientoCajaResponse = z.infer<typeof movimientoCajaResponseSchema>;
export type Cheque = z.infer<typeof chequeSchema>;
export type ChequePagina = z.infer<typeof chequePaginaSchema>;
export type ChequeResponse = z.infer<typeof chequeResponseSchema>;
