/** Lógica pura de la pantalla de caja: sin React, sin red, sin DOM.
 *
 * Igual que en cuenta corriente, acá vive el estado de NAVEGACIÓN (que viaja en la URL) y las
 * traducciones de vocabulario. `parseBusqueda` es la pieza crítica: la usa el `validateSearch` del
 * router y es lo único que separa una URL escrita a mano de un crash. */

export type Solapa = "caja" | "cartera";

export interface Busqueda {
  tab: Solapa;
  /** Filtro de forma en el extracto. `null` = todas. */
  forma: string | null;
  /** Filtro de estado en la cartera. `null` = todos. */
  estado: string | null;
  /** Página del extracto, 1-based. */
  page: number;
  /** Página de la cartera, 1-based. Separada de `page` a propósito: son dos paginaciones
   *  independientes, y colapsarlas haría que avanzar en una resetee la otra. */
  cpage: number;
}

export const BUSQUEDA_INICIAL: Busqueda = {
  tab: "caja",
  forma: null,
  estado: null,
  page: 1,
  cpage: 1,
};

/** Las cuatro formas del vocabulario (`app/core/formas_pago.py`). */
export const FORMAS = ["efectivo", "cheque", "transferencia", "tarjeta"] as const;

/** Los estados del papel (`ESTADOS_CHEQUE` de la migración 0011). */
export const ESTADOS_CHEQUE = [
  "en_cartera",
  "depositado",
  "cobrado",
  "rechazado",
  "entregado",
  "anulado",
] as const;

/** Los conceptos que el operador SÍ puede cargar a mano (`CONCEPTOS_MANUALES`).
 *
 * Los derivados no se ofrecen porque no se cargan a mano: los emite el documento que los genera. Si
 * alguno se colara igual, el backend lo rechaza dos veces (Pydantic y el service). Esta lista es la
 * comodidad, no la reja. */
export const CONCEPTOS_MANUALES = [
  { id: "gasto", label: "Gasto", signo: "egreso" },
  { id: "retiro", label: "Retiro", signo: "egreso" },
  { id: "otro_egreso", label: "Otro egreso", signo: "egreso" },
  { id: "aporte", label: "Aporte", signo: "ingreso" },
  { id: "otro_ingreso", label: "Otro ingreso", signo: "ingreso" },
] as const;

const ETIQUETA_CONCEPTO: Record<string, string> = {
  cobranza: "Cobranza",
  cheque_cobrado: "Cheque cobrado",
  cheque_cobrado_cartera: "Cheque sale de cartera",
  anulacion_pago: "Anulación de pago",
  aporte: "Aporte",
  otro_ingreso: "Otro ingreso",
  pago_proveedor: "Pago a proveedor",
  cheque_rechazado: "Cheque rechazado",
  anulacion_cobranza: "Anulación de cobranza",
  gasto: "Gasto",
  retiro: "Retiro",
  otro_egreso: "Otro egreso",
};

/** El concepto en castellano. Si aparece uno que esta tabla no conoce se muestra el crudo con los
 *  guiones bajos cambiados: es feo pero legible, y es mejor que una fila vacía. */
export function etiquetaConcepto(concepto: string): string {
  return ETIQUETA_CONCEPTO[concepto] ?? concepto.replace(/_/g, " ");
}

const ETIQUETA_ESTADO: Record<string, string> = {
  en_cartera: "En cartera",
  depositado: "Depositado",
  cobrado: "Cobrado",
  rechazado: "Rechazado",
  entregado: "Entregado",
  anulado: "Anulado",
};

export function etiquetaEstado(estado: string): string {
  return ETIQUETA_ESTADO[estado] ?? estado.replace(/_/g, " ");
}

const ETIQUETA_FORMA: Record<string, string> = {
  efectivo: "Efectivo",
  cheque: "Cheques en cartera",
  transferencia: "Transferencias",
  tarjeta: "Tarjeta",
};

export function etiquetaForma(forma: string): string {
  return ETIQUETA_FORMA[forma] ?? forma;
}

/** Un saldo negativo es FÍSICAMENTE imposible: nadie sacó plata que no estaba.
 *
 * Se calcula acá con `Number` y no con la plata-como-string porque es una COMPARACIÓN para decidir
 * qué pintar, no un cálculo cuyo resultado se guarde o se muestre. Lo que se muestra sigue siendo
 * el string original. */
export function estaEnNegativo(saldo: string): boolean {
  return Number(saldo) < 0;
}

/** El mismo texto que devuelve el backend en `advertencias`, pero para el estado PERSISTENTE de la
 *  pantalla: un toast se va y el problema queda. */
export function avisoDeNegativo(forma: string, saldo: string): string {
  return `${etiquetaForma(forma)} está en negativo (${saldo}). Eso no puede pasar en la realidad: revisá si falta cargar un ingreso.`;
}

function aPaginaValida(v: unknown): number {
  const n = Number(v);
  return Number.isInteger(n) && n >= 1 ? n : 1;
}

function aOpcion(v: unknown, validas: readonly string[]): string | null {
  return typeof v === "string" && validas.includes(v) ? v : null;
}

/** Sanea lo que venga en la URL. Nada de esto puede tirar una excepción: un search param
 *  manipulado tiene que degradar al default, no romper la pantalla.
 *
 * Los filtros se validan contra el vocabulario en vez de aceptar cualquier string: mandar
 * `?forma=bitcoin` al backend daría un 422 y la pantalla mostraría un error de red por algo que se
 * puede resolver acá sin pedir nada. */
export function parseBusqueda(search: Record<string, unknown>): Busqueda {
  return {
    tab: search.tab === "cartera" ? "cartera" : "caja",
    forma: aOpcion(search.forma, FORMAS),
    estado: aOpcion(search.estado, ESTADOS_CHEQUE),
    page: aPaginaValida(search.page),
    cpage: aPaginaValida(search.cpage),
  };
}

/** Cambiar de solapa limpia lo que era relativo a la anterior.
 *
 * Sin esto, volver a "Caja" después de filtrar la cartera por `depositado` dejaría un filtro
 * invisible aplicado a otra cosa — y la pantalla estaría mintiendo sin decir por qué. */
export function cambiarSolapa(actual: Busqueda, tab: Solapa): Busqueda {
  return { ...BUSQUEDA_INICIAL, tab: tab === actual.tab ? actual.tab : tab };
}

export function filtrarForma(actual: Busqueda, forma: string | null): Busqueda {
  return { ...actual, forma, page: 1 };
}

export function filtrarEstado(actual: Busqueda, estado: string | null): Busqueda {
  return { ...actual, estado, cpage: 1 };
}
