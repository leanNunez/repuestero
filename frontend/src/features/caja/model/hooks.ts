import { keepPreviousData, useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import {
  chequePaginaSchema,
  chequeResponseSchema,
  movimientoCajaPaginaSchema,
  movimientoCajaResponseSchema,
  saldoCajaSchema,
  type ChequeResponse,
  type MovimientoCajaResponse,
} from "@/entities/caja/schema";
import { apiGet, apiPost } from "@/shared/api/client";

/** Movimientos por página en el extracto. */
export const MOV_PAGE_SIZE = 25;
/** Cheques por página en la cartera. */
export const CARTERA_PAGE_SIZE = 20;

/** Las transiciones del papel. Los nombres son los del backend: esta lista es para ARMAR la URL,
 *  no para decidir cuál se puede hacer — eso lo dice el estado que devuelve el servidor. */
export type Transicion = "depositar" | "cobrar" | "rechazar" | "entregar";

export function useSaldoCaja() {
  return useQuery({
    queryKey: ["caja", "saldo"],
    queryFn: () => apiGet("/caja/saldo", saldoCajaSchema),
  });
}

export function useMovimientosCaja(forma: string | null, page: number) {
  return useQuery({
    queryKey: ["caja", "movimientos", forma, page],
    queryFn: () => {
      const params = new URLSearchParams({
        limite: String(MOV_PAGE_SIZE),
        offset: String((page - 1) * MOV_PAGE_SIZE),
      });
      if (forma) params.set("forma", forma);

      return apiGet(`/caja/movimientos?${params}`, movimientoCajaPaginaSchema);
    },
    placeholderData: keepPreviousData,
  });
}

export function useCartera(estado: string | null, page: number) {
  return useQuery({
    queryKey: ["caja", "cheques", estado, page],
    queryFn: () => {
      const params = new URLSearchParams({
        limite: String(CARTERA_PAGE_SIZE),
        offset: String((page - 1) * CARTERA_PAGE_SIZE),
      });
      if (estado) params.set("estado", estado);

      return apiGet(`/caja/cheques?${params}`, chequePaginaSchema);
    },
    placeholderData: keepPreviousData,
  });
}

interface MovimientoVars {
  concepto: string;
  forma: string;
  monto: string;
  detalle: string | null;
  fecha: string;
}

/** Alta manual de un movimiento. NO se manda el signo: lo determina el concepto en el backend.
 *
 * La respuesta puede traer `advertencias` (la caja quedó en negativo) con un 201: la operación se
 * acepta igual. Advertir no es bloquear, así que esto NO es un error y no va por `onError`. */
export function useRegistrarMovimiento() {
  const qc = useQueryClient();

  return useMutation<MovimientoCajaResponse, Error, MovimientoVars>({
    mutationFn: (vars) => apiPost("/caja/movimientos", vars, movimientoCajaResponseSchema),
    // Sin retry: un 422 de negocio ("no existe ese concepto") lo tiene que leer la persona.
    retry: false,
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: ["caja"] });
      void qc.invalidateQueries({ queryKey: ["dashboard"] });
    },
  });
}

/** Una transición del papel. Puede mover DOS formas a la vez (cobrar saca de la cartera y acredita
 *  en efectivo o transferencia), por eso la respuesta trae todos los saldos. */
export function useTransicionCheque() {
  const qc = useQueryClient();

  return useMutation<ChequeResponse, Error, { id: number; transicion: Transicion }>({
    mutationFn: ({ id, transicion }) =>
      apiPost(`/caja/cheques/${id}/${transicion}`, {}, chequeResponseSchema),
    // Sin retry: los 422 de acá son la máquina de estados ("un cheque cobrado no puede pasar a
    // cobrado"). Reintentar a ciegas no cambia nada y esconde el motivo.
    retry: false,
    onSuccess: () => {
      // Invalida saldo, extracto Y cartera de una: una transición mueve las tres cosas.
      void qc.invalidateQueries({ queryKey: ["caja"] });
      void qc.invalidateQueries({ queryKey: ["dashboard"] });
    },
  });
}

/** Conciliar contra el resumen bancario. La fecha es obligatoria: sin ella no se puede auditar, y
 *  el CHECK de la 0011 la exige igual. */
export function useConciliarCheque() {
  const qc = useQueryClient();

  return useMutation<unknown, Error, { id: number; fecha: string }>({
    mutationFn: ({ id, fecha }) => apiPost(`/caja/cheques/${id}/conciliar`, { fecha }),
    retry: false,
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: ["caja", "cheques"] });
    },
  });
}
