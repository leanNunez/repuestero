import { keepPreviousData, useQuery } from "@tanstack/react-query";

import {
  articuloListaSchema,
  articuloPaginaSchema,
  articuloSchema,
  opcionesSchema,
  type ArticuloPagina,
} from "@/entities/articulo/schema";
import { apiGet } from "@/shared/api/client";

/** Filas por página en el listado. Único lugar de verdad: la página y el offset se derivan de acá. */
export const PAGE_SIZE = 25;

/** Con texto → búsqueda híbrida (acotada, sin paginar); sin texto → listado paginado + filtros.
 *
 * Devuelve la MISMA forma `{ items, total }` en los dos modos, así la página no ramifica: en
 * búsqueda el `total` es simplemente cuántos resultados volvieron (conjunto acotado en memoria). */
export function useCatalogo(
  q: string,
  page: number,
  rubro: string,
  marca: string,
): ReturnType<typeof useQuery<ArticuloPagina>> {
  const query = q.trim();

  return useQuery({
    queryKey: query
      ? ["catalogo", "buscar", query]
      : ["catalogo", "listado", page, rubro, marca],
    queryFn: async (): Promise<ArticuloPagina> => {
      if (query) {
        const items = await apiGet(
          `/catalogo/buscar?q=${encodeURIComponent(query)}&limite=30`,
          articuloListaSchema,
        );
        return { items, total: items.length };
      }
      const params = new URLSearchParams({
        limite: String(PAGE_SIZE),
        offset: String((page - 1) * PAGE_SIZE),
      });
      if (rubro) params.set("rubro", rubro);
      if (marca) params.set("marca", marca);
      return apiGet(`/catalogo/articulos?${params.toString()}`, articuloPaginaSchema);
    },
    placeholderData: keepPreviousData,
  });
}

/** Rubros del catálogo completo (no de la página) para el dropdown. Cambian poco → cacheados. */
export function useRubros() {
  return useQuery({
    queryKey: ["catalogo", "rubros"],
    queryFn: () => apiGet("/catalogo/rubros", opcionesSchema),
    staleTime: 5 * 60 * 1000,
  });
}

export function useMarcas() {
  return useQuery({
    queryKey: ["catalogo", "marcas"],
    queryFn: () => apiGet("/catalogo/marcas", opcionesSchema),
    staleTime: 5 * 60 * 1000,
  });
}

export function useArticulo(codigo: string) {
  return useQuery({
    queryKey: ["articulo", codigo],
    queryFn: () =>
      apiGet(`/catalogo/articulos/${encodeURIComponent(codigo)}`, articuloSchema),
  });
}
