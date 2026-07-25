/** Lógica pura de la pantalla de cuenta corriente: sin React, sin red, sin DOM.
 *
 * A diferencia de ventas y compras acá NO hay reducer. El único dato que el operador tipea es un
 * monto: un `useState` local alcanza, y la validación vive acá para poder testearla sin montar
 * nada. Los reducers del proyecto existen donde hay renglones que se agregan y se sacan.
 *
 * Lo que sí vive acá es el estado de NAVEGACIÓN, que viaja en la URL (solapa, búsqueda, página,
 * cuenta seleccionada). `parseBusqueda` es la pieza crítica: la usa el `validateSearch` del router
 * y es lo único que separa una URL escrita a mano de un crash. */

import type { Movimiento } from "@/entities/cuenta-corriente/schema";

export type Solapa = "clientes" | "proveedores";

export interface Busqueda {
  tab: Solapa;
  /** Texto del buscador de cuentas. */
  q: string;
  /** Página del LISTADO de cuentas, 1-based. */
  page: number;
  /** Cuenta seleccionada, o null si no hay detalle abierto. */
  sel: number | null;
  /** Página del EXTRACTO, 1-based. Separada de `page` a propósito: son dos paginaciones
   *  independientes, y colapsarlas haría que avanzar en el extracto resetee el listado. */
  mpage: number;
  /** Mostrar también las cuentas en cero (por defecto se ven solo las que tienen saldo). */
  todos: boolean;
}

export const BUSQUEDA_INICIAL: Busqueda = {
  tab: "clientes",
  q: "",
  page: 1,
  sel: null,
  mpage: 1,
  todos: false,
};

function aPaginaValida(v: unknown): number {
  const n = Number(v);
  return Number.isInteger(n) && n >= 1 ? n : 1;
}

/** Sanea lo que venga en la URL. Nada de esto puede tirar una excepción: un search param
 *  manipulado tiene que degradar al default, no romper la pantalla. */
export function parseBusqueda(search: Record<string, unknown>): Busqueda {
  const sel = Number(search.sel);

  return {
    tab: search.tab === "proveedores" ? "proveedores" : "clientes",
    q: typeof search.q === "string" ? search.q : "",
    page: aPaginaValida(search.page),
    sel: Number.isInteger(sel) && sel > 0 ? sel : null,
    mpage: aPaginaValida(search.mpage),
    todos: search.todos === true || search.todos === "true",
  };
}

/** Cambiar de solapa limpia TODO lo que era relativo a la anterior.
 *
 * `sel` sobre todo: un id de cliente arrastrado a la solapa de proveedores puede acertarle a un
 * proveedor que existe, y mostrarías la cuenta equivocada sin ningún error. */
export function cambiarSolapa(b: Busqueda, tab: Solapa): Busqueda {
  return { ...b, tab, q: "", page: 1, sel: null, mpage: 1 };
}

/** Seleccionar una cuenta abre su extracto en la primera página. Conserva `q` y `page` para no
 *  perder el lugar del listado. */
export function seleccionar(b: Busqueda, id: number): Busqueda {
  return { ...b, sel: id, mpage: 1 };
}

/** Buscar vuelve al principio del listado y cierra el detalle: la cuenta abierta probablemente
 *  ya no esté entre los resultados. */
export function buscar(b: Busqueda, q: string): Busqueda {
  return { ...b, q, page: 1, sel: null, mpage: 1 };
}

export function verTodos(b: Busqueda, todos: boolean): Busqueda {
  return { ...b, todos, page: 1 };
}

/** Un monto imputable: positivo y con punto decimal.
 *
 * Rechaza la coma a propósito. `Number("10,50")` es NaN y el backend recibiría basura; es el
 * mismo criterio que ya aplican ventas y compras. Los formularios usan `CampoMoneda`, que muestra
 * la máscara es-AR y emite el valor canónico, así que la coma no llega nunca hasta acá. */
export function montoValido(monto: string): boolean {
  const limpio = monto.trim();
  if (limpio === "" || limpio.includes(",")) return false;

  const n = Number(limpio);
  return Number.isFinite(n) && n > 0;
}

const ETIQUETAS: Record<string, string> = {
  venta: "Venta",
  cobranza: "Cobranza",
  nota_credito: "Nota de crédito",
  compra: "Compra",
  pago: "Pago",
  ajuste: "Ajuste",
};

/** Etiqueta legible del tipo de movimiento. Un tipo desconocido devuelve el crudo en vez de
 *  romper: el importador de Paradox puede traer tipos que este front no conoce. */
export function etiquetaTipo(tipo: string): string {
  return ETIQUETAS[tipo] ?? tipo;
}

// --------------------------------------------------------------------------------- ajustes

/** Qué está haciendo el formulario de ajuste. `null` = cerrado.
 *
 * Un solo estado gobierna todo: el toggle abre en `libre`, el botón Revertir de una fila abre en
 * `storno` con ese movimiento, y cancelar vuelve a `null`. Espeja la decisión del backend, donde
 * la reversa y el ajuste manual son UN endpoint con dos modos. */
export type ModoAjuste = { kind: "libre" } | { kind: "storno"; movimiento: Movimiento };

/** Lo que se manda al endpoint de ajustes. La plata viaja como string, como en todo el módulo. */
export interface AjustePayload {
  motivo: string;
  debe?: string;
  haber?: string;
  revierte_movimiento_id?: number;
}

/** Qué tipos de movimiento se pueden revertir, por solapa.
 *
 * OJO: esto DUPLICA `MOVIMIENTOS_REVERSIBLES` de `app/ventas/service.py` y `app/compras/service.py`.
 * Vive acá porque el front tiene que decidir si dibuja el botón sin preguntarle al servidor. Si
 * cambia una lista hay que cambiar la otra — pero el modo de fallar es seguro: el backend rechaza
 * igual con un 422 legible, así que una divergencia molesta, no corrompe. */
const REVERSIBLES: Record<Solapa, readonly string[]> = {
  clientes: ["cobranza", "ajuste"],
  proveedores: ["pago", "ajuste"],
};

/** Si este movimiento se puede revertir desde el extracto.
 *
 * Un movimiento ya anulado no: revertirlo dos veces duplicaría la corrección, y el índice único
 * de la base lo rechazaría de todas formas. */
export function esReversible(tab: Solapa, m: Movimiento): boolean {
  return !m.anulado && REVERSIBLES[tab].includes(m.tipo);
}

/** Un motivo escrito de verdad. Mismo mínimo que el `min_length=3` del schema del backend.
 *
 * No es burocracia: un ajuste sin motivo es una fila que en seis meses nadie puede explicar, y el
 * CHECK de la base la rechaza. */
export function motivoValido(motivo: string): boolean {
  return motivo.trim().length >= 3;
}

/** El contra-asiento que va a generar una reversa, SOLO para mostrarlo antes de confirmar.
 *
 * El importe que vale lo calcula el backend leyendo el movimiento original — este es un espejo de
 * cortesía para que la persona vea qué va a pasar. Nunca se manda. */
export function espejoDelMovimiento(m: Movimiento): { columna: "Debe" | "Haber"; importe: string } {
  return Number(m.haber) > 0
    ? { columna: "Debe", importe: m.haber }
    : { columna: "Haber", importe: m.debe };
}

export type SignoSaldo = "deudor" | "a-favor" | "cero";

/** Un saldo negativo NO es lo mismo que cero: es plata a favor de la otra parte. */
export function signoSaldo(saldo: string): SignoSaldo {
  const n = Number(saldo);
  if (!Number.isFinite(n) || n === 0) return "cero";
  return n > 0 ? "deudor" : "a-favor";
}

/** Si la cuenta se pasó de su límite de crédito.
 *
 * Un límite en 0 (el default de `limite_cta_cte`) significa "sin límite fijado", no "límite
 * cero": no se excede nunca. Los proveedores no tienen límite y llegan en null.
 *
 * OJO: esto es informativo. Hoy NADIE hace cumplir el límite —ni al vender a cuenta corriente—,
 * así que una cuenta excedida se pinta pero no bloquea nada. */
export function excedeLimite(saldo: string, limite: string | null): boolean {
  if (limite === null) return false;

  const tope = Number(limite);
  const debe = Number(saldo);
  if (!Number.isFinite(tope) || !Number.isFinite(debe) || tope <= 0) return false;

  return debe > tope;
}
