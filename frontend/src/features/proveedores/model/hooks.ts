import { useQuery } from "@tanstack/react-query";

import { proveedorListaSchema } from "@/entities/proveedor/schema";
import { apiGet } from "@/shared/api/client";

export function useProveedores() {
  return useQuery({
    queryKey: ["proveedores"],
    queryFn: () => apiGet("/proveedores", proveedorListaSchema),
  });
}
