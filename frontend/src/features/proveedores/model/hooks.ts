import { keepPreviousData, useQuery } from "@tanstack/react-query";

import { proveedorPaginaSchema } from "@/entities/proveedor/schema";
import { queryPadron } from "@/features/proveedores/model/estado";
import { apiGet } from "@/shared/api/client";

/** Una página del padrón, con búsqueda opcional por razón social, código o CUIT.
 *
 * La búsqueda va SERVER-SIDE, no filtrando en memoria lo que ya vino: filtrar la página actual
 * buscaría dentro de 25 y diría "no existe" de alguien que sí está.
 *
 * `keepPreviousData` mantiene la tabla en pantalla mientras carga la página siguiente. Sin eso
 * cada click de paginado la vacía y la vuelve a llenar, que se lee como si algo se hubiera roto.
 */
export function useProveedores(q = "", page = 1) {
  const query = q.trim();

  return useQuery({
    queryKey: ["proveedores", "listado", query, page],
    queryFn: () => apiGet(`/proveedores?${queryPadron(query, page)}`, proveedorPaginaSchema),
    placeholderData: keepPreviousData,
  });
}
