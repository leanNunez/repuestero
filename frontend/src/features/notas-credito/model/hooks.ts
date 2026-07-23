import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import {
  notaCreditoResponseSchema,
  renglonesAcreditablesSchema,
  type NotaCreditoResponse,
} from "@/entities/nota-credito/schema";
import { apiGet, apiPost } from "@/shared/api/client";

/** Lo que resta acreditar de cada renglón de una venta: precarga el flujo de NC y fija los
 * máximos. Se dispara solo cuando hay una venta elegida (el diálogo abierto). */
export function useRenglonesAcreditables(ventaId: number | null) {
  return useQuery({
    queryKey: ["acreditable", ventaId],
    queryFn: () => apiGet(`/ventas/${ventaId}/acreditable`, renglonesAcreditablesSchema),
    enabled: ventaId !== null,
  });
}

interface EmitirArgs {
  comprobante_id: number;
  renglones: { articulo_codigo: string; cantidad: string }[];
}

export function useEmitirNotaCredito() {
  const qc = useQueryClient();

  return useMutation<NotaCreditoResponse, Error, EmitirArgs>({
    mutationFn: (args) => apiPost("/ventas/notas-credito", args, notaCreditoResponseSchema),
    // Sin retry: un 409 de numeración o un 422 de negocio los tiene que leer la persona.
    retry: false,
    onSuccess: () => {
      // La NC devolvió stock y (si era a crédito) movió el saldo: lo de pantalla quedó viejo.
      void qc.invalidateQueries({ queryKey: ["ventas"] });
      void qc.invalidateQueries({ queryKey: ["catalogo"] });
      void qc.invalidateQueries({ queryKey: ["dashboard"] });
      void qc.invalidateQueries({ queryKey: ["notas-credito"] });
    },
  });
}
