import { useQuery } from "@tanstack/react-query";

import { articuloListaSchema } from "@/entities/articulo/schema";
import { apiGet } from "@/shared/api/client";

export interface ConsultaCompat {
  marca: string;
  modelo: string;
  anio: string;
}

/** Busca repuestos que sirven para un vehículo. Solo corre cuando `enabled` (marca+modelo). */
export function useCompatibilidad(consulta: ConsultaCompat, enabled: boolean) {
  const { marca, modelo, anio } = consulta;
  return useQuery({
    queryKey: ["compatibilidad", marca, modelo, anio],
    queryFn: () => {
      const qs = new URLSearchParams({ marca, modelo });
      if (anio) qs.set("anio", anio);
      return apiGet(`/compatibilidad/repuestos?${qs.toString()}`, articuloListaSchema);
    },
    enabled,
  });
}
