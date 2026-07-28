import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import {
  clienteListaSchema,
  clienteSchema,
  type Cliente,
  type ClienteCrear,
} from "@/entities/cliente/schema";
import { apiGet, apiPost } from "@/shared/api/client";

export function useClientes() {
  return useQuery({
    queryKey: ["clientes"],
    queryFn: () => apiGet("/clientes", clienteListaSchema),
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
