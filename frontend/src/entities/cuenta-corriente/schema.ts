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
  /** Cuándo se REGISTRÓ, contra `fecha`, que es cuándo pasó. Con movimientos retroactivos las dos
   *  dejan de coincidir: mostrarlas es lo que hace auditable al retroactivo. */
  creado_en: z.string(),
  /** Si un ajuste posterior ya revirtió este movimiento. Sin esto el extracto mostraría un haber
   *  y su contra-debe sin ninguna pista de que se cancelan entre sí. */
  anulado: z.boolean(),
  /** La respuesta del backend a "¿puedo apretar Revertir en esta fila?". Ya contempla que un
   *  movimiento anulado no se revierte de nuevo, así que el front no combina nada: dibuja el
   *  botón si esto es true. La regla de QUÉ es reversible vive solo en los services de Python. */
  reversible: z.boolean(),
  /** Lo mismo para ANULAR, que es la operación que reemplazó a Revertir en las cobranzas y los
   *  pagos: cuando el recibo empezó a mover caja y cartera, revertir solo el ledger dejaba esas dos
   *  cosas vivas. Anular el documento revierte las tres en una transacción.
   *
   *  Viaja calculado por la misma razón que `reversible`: deducirlo acá de `ref_tipo` pondría la
   *  regla en dos lugares. El id del documento a anular está en `ref_id`. */
  anulable: z.boolean(),
  /** Saldo después de este movimiento. Lo calcula el backend sobre TODO el ledger: no se
   *  recalcula acá, porque el front solo tiene una página. */
  saldo_acumulado: z.string(),
});

export const movimientoPaginaSchema = z.object({
  items: z.array(movimientoSchema),
  total: z.number(),
  cuenta: cuentaSchema,
});

/** Con qué se cobró o se pagó un renglón del documento (`FormaPagoLeer`).
 *
 * En esta etapa `cheque` es solo la etiqueta con su monto: banco, número y fecha de cobro llegan
 * con el módulo de caja, y ahí cada renglón se convierte en un cheque de la cartera. */
export const formaPagoSchema = z.object({
  forma: z.string(),
  monto: z.string(),
});

/** Acuse de una cobranza o de un pago.
 *
 * Las claves del documento son NEUTRAS (`documento_*`, no `recibo_*`) porque el backend devuelve
 * las mismas para las dos solapas: del lado clientes el documento es un RECIBO, del lado
 * proveedores una ORDEN DE PAGO. Un solo schema, sin `if tab === "clientes"` en el hook.
 *
 * Está SEPARADO del de ajustes a propósito. Antes era uno solo para las cuatro mutaciones —Zod
 * descarta las claves que no declara—, pero al declarar `documento_*` como requeridas la respuesta
 * de un ajuste, que no las trae, fallaría la validación. */
export const imputacionResponseSchema = z.object({
  movimiento_id: z.number(),
  saldo: z.string(),
  documento_id: z.number(),
  /** 'REC' (recibo) o 'OP' (orden de pago). */
  documento_tipo: z.string(),
  documento_pto_venta: z.number(),
  documento_numero: z.number(),
});

/** Acuse de un ajuste: no emite documento, así que solo trae el movimiento y el saldo. */
export const ajusteResponseSchema = z.object({
  movimiento_id: z.number(),
  saldo: z.string(),
});

export type Cuenta = z.infer<typeof cuentaSchema>;
export type CuentaPagina = z.infer<typeof cuentaPaginaSchema>;
export type Movimiento = z.infer<typeof movimientoSchema>;
export type MovimientoPagina = z.infer<typeof movimientoPaginaSchema>;
export type FormaPago = z.infer<typeof formaPagoSchema>;
export type ImputacionResponse = z.infer<typeof imputacionResponseSchema>;
export type AjusteResponse = z.infer<typeof ajusteResponseSchema>;
