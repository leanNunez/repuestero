import { useQuery } from "@tanstack/react-query";

import { clienteListaSchema } from "@/entities/cliente/schema";
import { apiGet } from "@/shared/api/client";

export function useClientes() {
  return useQuery({
    queryKey: ["clientes"],
    queryFn: () => apiGet("/clientes", clienteListaSchema),
  });
}
