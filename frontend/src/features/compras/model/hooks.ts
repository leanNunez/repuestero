import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import {
  compraPaginaSchema,
  compraResponseSchema,
  type CompraResponse,
} from "@/entities/compra/schema";
import { apiGet, apiPost } from "@/shared/api/client";

import type { Estado } from "./estado";

/** Últimas compras registradas, para el listado del mostrador de compras. */
export function useCompras() {
  return useQuery({
    queryKey: ["compras"],
    queryFn: () => apiGet("/compras?limite=20", compraPaginaSchema),
  });
}

function aPayload(estado: Estado) {
  return {
    proveedor_codigo: estado.proveedorCodigo,
    deposito_codigo: estado.deposito.trim(),
    numero_comprobante: estado.numeroComprobante.trim(),
    condicion: estado.condicion,
    renglones: estado.renglones.map((r) => ({
      articulo_codigo: r.articulo_codigo,
      cantidad: r.cantidad,
      costo_unitario: r.costo_unitario,
    })),
  };
}

export function useEmitirCompra() {
  const qc = useQueryClient();

  return useMutation<CompraResponse, Error, Estado>({
    mutationFn: (estado) => apiPost("/compras", aPayload(estado), compraResponseSchema),
    // Sin retry: un 409 (factura ya cargada) o un 422 de negocio los tiene que leer la persona.
    retry: false,
    onSuccess: () => {
      // La compra sumó stock, actualizó el costo y repriceó: lo de pantalla quedó viejo.
      void qc.invalidateQueries({ queryKey: ["compras"] });
      void qc.invalidateQueries({ queryKey: ["catalogo"] });
      void qc.invalidateQueries({ queryKey: ["dashboard"] });
    },
  });
}
