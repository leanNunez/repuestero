import { keepPreviousData, useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import {
  proveedorPaginaSchema,
  proveedorSchema,
  type Proveedor,
  type ProveedorCrear,
} from "@/entities/proveedor/schema";
import { queryPadron } from "@/features/proveedores/model/estado";
import { apiGet, apiPost } from "@/shared/api/client";

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

/** Alta de proveedor. El código NO viaja en el body: lo asigna el servidor y vuelve en la
 *  respuesta, que es la única fuente de verdad sobre qué número le tocó. */
export function useCrearProveedor() {
  const qc = useQueryClient();

  return useMutation<Proveedor, Error, ProveedorCrear>({
    mutationFn: (vars) => apiPost("/proveedores", vars, proveedorSchema),
    // Sin retry: los errores de acá son de negocio (422 por CUIT, 409 por código). Reintentar a
    // ciegas no cambia el resultado y, si el alta llegó a escribir, duplicaría el proveedor.
    retry: false,
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: ["proveedores"] });
    },
  });
}
