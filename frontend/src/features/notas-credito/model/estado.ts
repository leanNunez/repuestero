/** El estado de una nota de crédito en curso: qué se acredita de cada renglón de una venta.
 *
 * Vive en un useReducer LOCAL del diálogo, no en Zustand (mismo criterio que la venta): una NC a
 * medio armar es válida solo mientras el diálogo está abierto. Arranca con cada renglón en su
 * máximo acreditable (una anulación TOTAL por defecto); el operador baja las cantidades para una
 * parcial.
 */

import type { RenglonAcreditable } from "@/entities/nota-credito/schema";

export interface RenglonNC {
  articulo_codigo: string;
  descripcion: string;
  precio_unitario: string; // neto, sin IVA (congelado del original)
  alicuota_iva: number; // solo para el total en pantalla
  cantidad_acreditable: string; // el máximo: lo que resta acreditar de este renglón
  cantidad_acreditar: string; // lo que el operador decide acreditar (editable)
}

export interface Estado {
  renglones: RenglonNC[];
}

export const ESTADO_INICIAL: Estado = { renglones: [] };

export type Accion =
  | { type: "init"; renglones: RenglonNC[] }
  | { type: "cantidad"; i: number; valor: string }
  | { type: "reset" };

export function reducer(estado: Estado, accion: Accion): Estado {
  switch (accion.type) {
    case "init":
      return { renglones: accion.renglones };

    case "cantidad": {
      const renglones = [...estado.renglones];
      renglones[accion.i] = { ...renglones[accion.i], cantidad_acreditar: accion.valor };
      return { renglones };
    }

    case "reset":
      return ESTADO_INICIAL;
  }
}

/** Construye el estado inicial desde los renglones acreditables: cada uno en su máximo (total por
 * defecto). Los renglones ya totalmente acreditados (máximo 0) se omiten: no hay nada para hacer. */
export function desdeAcreditables(renglones: RenglonAcreditable[]): RenglonNC[] {
  return renglones
    .filter((r) => Number(r.cantidad_acreditable) > 0)
    .map((r) => ({
      articulo_codigo: r.articulo_codigo,
      descripcion: r.descripcion,
      precio_unitario: r.precio_unitario,
      alicuota_iva: Number(r.alicuota_iva),
      cantidad_acreditable: r.cantidad_acreditable,
      cantidad_acreditar: r.cantidad_acreditable,
    }));
}

/** Un renglón válido: la cantidad a acreditar es un número entre 0 y el máximo (no lo excede). */
export function renglonValido(r: RenglonNC): boolean {
  const cant = Number(r.cantidad_acreditar);
  return (
    r.cantidad_acreditar.trim().length > 0 &&
    Number.isFinite(cant) &&
    cant >= 0 &&
    cant <= Number(r.cantidad_acreditable)
  );
}

/** Se puede emitir si hay al menos un renglón con cantidad > 0 y ninguno se pasa del máximo. */
export function puedeEmitir(estado: Estado): boolean {
  return (
    estado.renglones.length > 0 &&
    estado.renglones.every(renglonValido) &&
    estado.renglones.some((r) => Number(r.cantidad_acreditar) > 0)
  );
}

export interface Totales {
  neto: number;
  iva: number;
  total: number;
}

/** Total en pantalla (solo presentación). El importe que se GUARDA lo calcula el backend por
 * renglón copiando el precio del original; esto es para que el operador vea a cuánto va la NC. */
export function totales(renglones: RenglonNC[]): Totales {
  let neto = 0;
  let iva = 0;
  for (const r of renglones) {
    const base = Number(r.cantidad_acreditar) * Number(r.precio_unitario);
    if (Number.isFinite(base) && base > 0) {
      neto += base;
      iva += (base * r.alicuota_iva) / 100;
    }
  }
  return { neto, iva, total: neto + iva };
}

/** Los renglones que van al POST: solo los que acreditan algo (cantidad > 0). */
export function aRenglonesPayload(estado: Estado): { articulo_codigo: string; cantidad: string }[] {
  return estado.renglones
    .filter((r) => Number(r.cantidad_acreditar) > 0)
    .map((r) => ({ articulo_codigo: r.articulo_codigo, cantidad: r.cantidad_acreditar }));
}
