import { keepPreviousData, useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import {
  clientePaginaSchema,
  clienteSchema,
  type Cliente,
  type ClienteCrear,
} from "@/entities/cliente/schema";
import { queryPadron } from "@/features/clientes/model/estado";
import { apiGet, apiPost } from "@/shared/api/client";

/** Una página del padrón, con búsqueda opcional por denominación, código o CUIT.
 *
 * La búsqueda va SERVER-SIDE, no filtrando en memoria lo que ya vino: filtrar la página actual
 * sobre 900 clientes buscaría dentro de 25 y diría "no existe" de alguien que sí está.
 *
 * `keepPreviousData` mantiene la tabla en pantalla mientras carga la página siguiente. Sin eso
 * cada click de paginado la vacía y la vuelve a llenar, que se lee como si algo se hubiera roto. */
export function useClientes(q = "", page = 1) {
  const query = q.trim();

  return useQuery({
    queryKey: ["clientes", "listado", query, page],
    queryFn: () => apiGet(`/clientes?${queryPadron(query, page)}`, clientePaginaSchema),
    placeholderData: keepPreviousData,
  });
}

/** Alta de cliente. El código NO viaja en el body: lo asigna el servidor y vuelve en la respuesta,
 *  que es la única fuente de verdad sobre qué número le tocó. */
export function useCrearCliente() {
  const qc = useQueryClient();

  return useMutation<Cliente, Error, ClienteCrear>({
    mutationFn: (vars) => apiPost("/clientes", vars, clienteSchema),
    // Sin retry: los errores de acá son de negocio (422 por CUIT, 409 por código). Reintentar a
    // ciegas no cambia el resultado y, si el alta llegó a escribir, duplicaría el cliente.
    retry: false,
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: ["clientes"] });
    },
  });
}
