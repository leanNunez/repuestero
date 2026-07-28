/** Lógica pura del padrón de proveedores. Sin React: se testea sin montar nada. */

import { queryPagina } from "@/shared/lib/paginacion";

/** Filas por página del padrón. Único lugar de verdad: la página y el offset se derivan de acá. */
export const PAGE_SIZE = 25;

/** Query string de una página del padrón de proveedores. */
export function queryPadron(q: string, page: number): string {
  return queryPagina(q, page, PAGE_SIZE);
}
