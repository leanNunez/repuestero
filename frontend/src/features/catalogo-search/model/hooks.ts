import { keepPreviousData, useQuery } from "@tanstack/react-query";

import {
  articuloListaSchema,
  articuloSchema,
} from "@/entities/articulo/schema";
import { apiGet } from "@/shared/api/client";

/** Con texto → búsqueda híbrida; sin texto → listado. Un solo hook para la página de catálogo. */
export function useCatalogo(q: string) {
  const query = q.trim();
  return useQuery({
    queryKey: ["catalogo", query],
    queryFn: () =>
      apiGet(
        query
          ? `/catalogo/buscar?q=${encodeURIComponent(query)}&limite=30`
          : `/catalogo/articulos?limite=50`,
        articuloListaSchema,
      ),
    placeholderData: keepPreviousData,
  });
}

export function useArticulo(codigo: string) {
  return useQuery({
    queryKey: ["articulo", codigo],
    queryFn: () =>
      apiGet(`/catalogo/articulos/${encodeURIComponent(codigo)}`, articuloSchema),
  });
}
