import { z } from "zod";

/** Espeja los contratos de cuenta corriente de `app/ventas/schemas.py` y `app/compras/schemas.py`.
 *
 * UN solo juego de schemas para las dos solapas: el backend devuelve deliberadamente las mismas
 * claves para clientes y proveedores (`nombre`, no `denominacion`/`razon_social`), justamente para
 * que acá no haya que duplicar nada.
 *
 * La plata viaja como STRING de punta a punta, igual que en ventas y compras: nunca pasa por
 * Number en el camino de escritura, para no perder centavos. `pesos()` la formatea solo para
 * mostrar. */

/** Una cuenta con su saldo (`CuentaLeer`). Saldo positivo = nos debe / le debemos. */
export const cuentaSchema = z.object({
  id: z.number(),
  /** Las cobranzas y pagos se imputan por CÓDIGO, no por id. */
  codigo: z.string(),
  nombre: z.string(),
  saldo: z.string(),
  /** Límite de crédito. Siempre null en proveedores: no tienen. */
  limite: z.string().nullable(),
});

export const cuentaPaginaSchema = z.object({
  items: z.array(cuentaSchema),
  total: z.number(),
  /** Neto del conjunto FILTRADO, no de la página. Mezcla signos. */
  saldo_total: z.string(),
});

/** Un renglón del extracto (`MovimientoLeer`). */
export const movimientoSchema = z.object({
  id: z.number(),
  fecha: z.string(),
  tipo: z.string(),
  debe: z.string(),
  haber: z.string(),
  ref_tipo: z.string().nullable(),
  ref_id: z.number().nullable(),
  /** Por qué se ajustó. Solo lo traen los movimientos de tipo 'ajuste'. */
  motivo: z.string().nullable(),
  /** Si un ajuste posterior ya revirtió este movimiento. Sin esto el extracto mostraría un haber
   *  y su contra-debe sin ninguna pista de que se cancelan entre sí. */
  anulado: z.boolean(),
  /** La respuesta del backend a "¿puedo apretar Revertir en esta fila?". Ya contempla que un
   *  movimiento anulado no se revierte de nuevo, así que el front no combina nada: dibuja el
   *  botón si esto es true. La regla de QUÉ es reversible vive solo en los services de Python. */
  reversible: z.boolean(),
  /** Saldo después de este movimiento. Lo calcula el backend sobre TODO el ledger: no se
   *  recalcula acá, porque el front solo tiene una página. */
  saldo_acumulado: z.string(),
});

export const movimientoPaginaSchema = z.object({
  items: z.array(movimientoSchema),
  total: z.number(),
  cuenta: cuentaSchema,
});

/** Acuse de una cobranza, un pago o un ajuste.
 *
 * `CobranzaResponse`, `PagoProveedorResponse` y los dos `AjusteResponse` solo difieren en
 * `cliente_id`/`proveedor_id`, y Zod descarta las claves que no declara: un schema alcanza para
 * las cuatro mutaciones. */
export const imputacionResponseSchema = z.object({
  movimiento_id: z.number(),
  saldo: z.string(),
});

export type Cuenta = z.infer<typeof cuentaSchema>;
export type CuentaPagina = z.infer<typeof cuentaPaginaSchema>;
export type Movimiento = z.infer<typeof movimientoSchema>;
export type MovimientoPagina = z.infer<typeof movimientoPaginaSchema>;
export type ImputacionResponse = z.infer<typeof imputacionResponseSchema>;
