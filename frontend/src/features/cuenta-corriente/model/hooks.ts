import { keepPreviousData, useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import {
  cuentaPaginaSchema,
  imputacionResponseSchema,
  movimientoPaginaSchema,
  type ImputacionResponse,
} from "@/entities/cuenta-corriente/schema";
import { apiGet, apiPost } from "@/shared/api/client";

import type { Solapa } from "./estado";

/** Cuentas por página en el listado. */
export const PAGE_SIZE = 20;
/** Movimientos por página en el extracto. */
export const MOV_PAGE_SIZE = 25;

/** Las dos solapas son el MISMO contrato contra dos prefijos distintos. */
const RUTA = {
  clientes: { base: "/ventas", coleccion: "clientes", campoCodigo: "cliente_codigo" },
  proveedores: { base: "/compras", coleccion: "proveedores", campoCodigo: "proveedor_codigo" },
} as const;

const IMPUTAR = {
  clientes: "/ventas/cobranzas",
  proveedores: "/compras/pagos",
} as const;

export function useCuentas(tab: Solapa, page: number, q: string, todos: boolean) {
  return useQuery({
    queryKey: ["cuenta-corriente", tab, "cuentas", page, q, todos],
    queryFn: () => {
      const params = new URLSearchParams({
        limite: String(PAGE_SIZE),
        offset: String((page - 1) * PAGE_SIZE),
        solo_con_saldo: String(!todos),
      });
      const texto = q.trim();
      if (texto) params.set("buscar", texto);

      return apiGet(`${RUTA[tab].base}/cuenta-corriente?${params}`, cuentaPaginaSchema);
    },
    placeholderData: keepPreviousData,
  });
}

export function useMovimientos(tab: Solapa, id: number | null, mpage: number) {
  const { base, coleccion } = RUTA[tab];

  return useQuery({
    queryKey: ["cuenta-corriente", tab, "movimientos", id, mpage],
    queryFn: () => {
      const params = new URLSearchParams({
        limite: String(MOV_PAGE_SIZE),
        offset: String((mpage - 1) * MOV_PAGE_SIZE),
      });
      return apiGet(`${base}/${coleccion}/${id}/movimientos?${params}`, movimientoPaginaSchema);
    },
    // Sin cuenta seleccionada no hay nada que pedir.
    enabled: id !== null,
    placeholderData: keepPreviousData,
  });
}

/** Cobranza (clientes) o pago (proveedores). Es la misma operación contra dos endpoints. */
export function useImputar(tab: Solapa) {
  const qc = useQueryClient();

  return useMutation<ImputacionResponse, Error, { codigo: string; monto: string }>({
    mutationFn: ({ codigo, monto }) =>
      apiPost(
        IMPUTAR[tab],
        { [RUTA[tab].campoCodigo]: codigo, monto },
        imputacionResponseSchema,
      ),
    // Sin retry: un 422 de negocio ("el monto debe ser mayor a cero") lo tiene que leer la persona.
    retry: false,
    onSuccess: () => {
      // Movió el saldo: el listado, el extracto y el KPI de deuda quedaron viejos. El prefijo
      // barre las dos solapas y las dos paginaciones de una.
      void qc.invalidateQueries({ queryKey: ["cuenta-corriente"] });
      void qc.invalidateQueries({ queryKey: ["dashboard"] });
      // NO se invalidan ["ventas"] ni ["compras"]: una cobranza no toca comprobantes ni stock.
    },
  });
}
