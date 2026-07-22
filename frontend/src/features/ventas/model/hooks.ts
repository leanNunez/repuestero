import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import {
  precioSugeridoSchema,
  ventaPaginaSchema,
  ventaResponseSchema,
  type PrecioSugerido,
  type VentaResponse,
} from "@/entities/venta/schema";
import { apiGet, apiPost } from "@/shared/api/client";

import type { Estado } from "./estado";

/** Últimas ventas emitidas, para el listado del mostrador. */
export function useVentas() {
  return useQuery({
    queryKey: ["ventas"],
    queryFn: () => apiGet("/ventas?limite=20", ventaPaginaSchema),
  });
}

/** Precio a precargar al agregar un artículo: el de la lista del cliente, o Mostrador. Es una
 * llamada suelta (no useQuery) porque se dispara en el momento del click, no en el render. */
export function fetchPrecioSugerido(
  articuloCodigo: string,
  clienteCodigo?: string,
): Promise<PrecioSugerido> {
  const params = new URLSearchParams({ articulo_codigo: articuloCodigo });
  if (clienteCodigo) params.set("cliente_codigo", clienteCodigo);
  return apiGet(`/ventas/precio-sugerido?${params.toString()}`, precioSugeridoSchema);
}

function aPayload(estado: Estado) {
  return {
    cliente_codigo: estado.clienteCodigo,
    deposito_codigo: estado.deposito.trim(),
    condicion: estado.condicion,
    renglones: estado.renglones.map((r) => ({
      articulo_codigo: r.articulo_codigo,
      cantidad: r.cantidad,
      precio_unitario: r.precio_unitario,
    })),
  };
}

export function useEmitirVenta() {
  const qc = useQueryClient();

  return useMutation<VentaResponse, Error, Estado>({
    mutationFn: (estado) => apiPost("/ventas", aPayload(estado), ventaResponseSchema),
    // Sin retry: un 409 de numeración o un 422 de negocio los tiene que leer la persona.
    retry: false,
    onSuccess: () => {
      // La venta bajó stock y (si es a crédito) movió el saldo: lo de pantalla quedó viejo.
      void qc.invalidateQueries({ queryKey: ["ventas"] });
      void qc.invalidateQueries({ queryKey: ["catalogo"] });
      void qc.invalidateQueries({ queryKey: ["dashboard"] });
    },
  });
}
