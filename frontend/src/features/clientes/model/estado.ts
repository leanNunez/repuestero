/** Lógica pura del alta de cliente. Sin React: se testea sin montar nada.
 *
 * El CUIT se valida ACÁ además de en el backend, y no es duplicación por descuido. El backend es
 * el que manda —esa validación no se toca— pero mandarle un CUIT que ya sabemos que está mal es
 * un viaje al servidor para volver con un error rojo que se podía evitar. Que el botón no se
 * habilite explica más rápido que un 422.
 */

import { cuitAceptable, cuitValido } from "@/shared/lib/cuit";
import { queryPagina } from "@/shared/lib/paginacion";

// Se re-exportan: eran de este módulo antes de mudarse a `shared/lib`, y los importa el formulario.
export { cuitAceptable, cuitValido };

/** Filas por página del padrón. Único lugar de verdad: la página y el offset se derivan de acá. */
export const PAGE_SIZE = 25;

/** Query string de una página del padrón de clientes. */
export function queryPadron(q: string, page: number): string {
  return queryPagina(q, page, PAGE_SIZE);
}

/** Espeja `app/core/cond_fiscal.py`. El orden es el del formulario: primero lo más frecuente en el
 *  mostrador. `EXENTO` va último porque casi no aparece. */
export const CONDICIONES_FISCALES = [
  { id: "CONSUMIDOR_FINAL", label: "Consumidor final" },
  { id: "MONOTRIBUTO", label: "Monotributo" },
  { id: "RESPONSABLE_INSCRIPTO", label: "Responsable inscripto" },
  { id: "EXENTO", label: "Exento" },
] as const;

export type CondFiscal = (typeof CONDICIONES_FISCALES)[number]["id"];

export interface FormularioCliente {
  denominacion: string;
  cuit: string;
  cond_fiscal: CondFiscal;
  limite_cta_cte: string;
  telefono: string;
  email: string;
  direccion: string;
}

export const VACIO: FormularioCliente = {
  denominacion: "",
  cuit: "",
  cond_fiscal: "CONSUMIDOR_FINAL",
  limite_cta_cte: "",
  telefono: "",
  email: "",
  direccion: "",
};

export function puedeGuardar(f: FormularioCliente): boolean {
  return f.denominacion.trim() !== "" && cuitAceptable(f.cuit);
}

/** Arma el body del POST. Los opcionales vacíos viajan como `null`, no como `""`: la columna es
 *  nullable y un string vacío es un dato que después hay que limpiar. */
export function aPayload(f: FormularioCliente) {
  const opcional = (v: string) => (v.trim() === "" ? null : v.trim());

  return {
    denominacion: f.denominacion.trim(),
    cuit: opcional(f.cuit),
    cond_fiscal: f.cond_fiscal,
    limite_cta_cte: f.limite_cta_cte === "" ? "0" : f.limite_cta_cte,
    telefono: opcional(f.telefono),
    email: opcional(f.email),
    direccion: opcional(f.direccion),
  };
}
