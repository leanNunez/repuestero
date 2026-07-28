/** Lógica pura del padrón y del alta de proveedor. Sin React: se testea sin montar nada. */

import { cuitAceptable } from "@/shared/lib/cuit";
import { queryPagina } from "@/shared/lib/paginacion";

export { cuitAceptable };

/** Filas por página del padrón. Único lugar de verdad: la página y el offset se derivan de acá. */
export const PAGE_SIZE = 25;

/** Query string de una página del padrón de proveedores. */
export function queryPadron(q: string, page: number): string {
  return queryPagina(q, page, PAGE_SIZE);
}

export interface FormularioProveedor {
  razon_social: string;
  cuit: string;
  telefono: string;
  email: string;
}

export const VACIO: FormularioProveedor = {
  razon_social: "",
  cuit: "",
  telefono: "",
  email: "",
};

/** Lo único obligatorio es la razón social. El resto se completa cuando se sabe: a un proveedor
 *  nuevo muchas veces se lo carga con el nombre que figura en el remito y nada más. */
export function puedeGuardar(f: FormularioProveedor): boolean {
  return f.razon_social.trim() !== "" && cuitAceptable(f.cuit);
}

/** Arma el body del POST. Los opcionales vacíos viajan como `null`, no como `""`: la columna es
 *  nullable y un string vacío es un dato que después hay que limpiar. */
export function aPayload(f: FormularioProveedor) {
  const opcional = (v: string) => (v.trim() === "" ? null : v.trim());

  return {
    razon_social: f.razon_social.trim(),
    cuit: opcional(f.cuit),
    telefono: opcional(f.telefono),
    email: opcional(f.email),
  };
}
