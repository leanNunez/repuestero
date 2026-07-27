import { keepPreviousData, useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import {
  ajusteResponseSchema,
  cuentaPaginaSchema,
  imputacionResponseSchema,
  movimientoPaginaSchema,
  type AjusteResponse,
  type ImputacionResponse,
} from "@/entities/cuenta-corriente/schema";
import { apiGet, apiPost } from "@/shared/api/client";

import type { AjustePayload, FormaPagoRenglon, Solapa } from "./estado";

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

/** Lo que hace falta para imputar: a quién, cuánto, cuándo y con qué. */
interface ImputarVars {
  codigo: string;
  monto: string;
  fecha: string;
  /** El detalle de con qué se cobró/pagó. El backend lo acepta omitido y asume efectivo por el
   *  total, pero desde acá siempre va explícito: la pantalla conoce el dato. */
  formasPago: readonly FormaPagoRenglon[];
}

/** Cobranza (clientes) o pago (proveedores). Es la misma operación contra dos endpoints.
 *
 * Emite un DOCUMENTO: un recibo del lado clientes, una orden de pago del lado proveedores. Por eso
 * la respuesta trae `documento_*` y no solo el movimiento. */
export function useImputar(tab: Solapa) {
  const qc = useQueryClient();

  return useMutation<ImputacionResponse, Error, ImputarVars>({
    // `fecha` viaja como string ISO tal cual la escupe el input, sin pasar nunca por `new Date`:
    // ver el docstring de `fechaCorta` en shared/lib/format.ts. Mismo criterio que la plata.
    mutationFn: ({ codigo, monto, fecha, formasPago }) =>
      apiPost(
        IMPUTAR[tab],
        {
          [RUTA[tab].campoCodigo]: codigo,
          monto,
          fecha,
          formas_pago: formasPago.map((f) => ({ forma: f.forma, monto: f.monto })),
        },
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

/** Anular el DOCUMENTO (recibo u orden de pago), no el movimiento del ledger.
 *
 * Es lo que reemplazó a "Revertir" en las cobranzas y los pagos. La diferencia no es de nombre:
 * revertir tocaba solo la cuenta corriente y dejaba vivos el ingreso de caja y el cheque que ese
 * recibo había generado. Anular revierte las tres cosas en UNA transacción del lado del servidor.
 *
 * Por eso invalida también `["caja"]`: el saldo del cajón y la cartera cambiaron. */
export function useAnularDocumento(tab: Solapa) {
  const qc = useQueryClient();
  const ruta = tab === "clientes" ? "/ventas/recibos" : "/compras/ordenes-pago";

  return useMutation<AjusteResponse, Error, { documentoId: number; motivo: string }>({
    mutationFn: ({ documentoId, motivo }) =>
      apiPost(`${ruta}/${documentoId}/anular`, { motivo }, ajusteResponseSchema),
    // Sin retry: un 422 acá es "ese recibo ya fue anulado", y reintentarlo a ciegas es justo lo que
    // el índice único parcial de la 0009 previene del lado de la base.
    retry: false,
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: ["cuenta-corriente"] });
      void qc.invalidateQueries({ queryKey: ["caja"] });
      void qc.invalidateQueries({ queryKey: ["dashboard"] });
    },
  });
}

/** Ajuste de cuenta corriente: reversa de un movimiento, o corrección manual.
 *
 * El ledger es append-only, así que esto es lo ÚNICO que puede arreglar una cobranza mal cargada.
 * Un solo endpoint para los dos modos, igual que el backend. */
export function useAjustar(tab: Solapa, cuentaId: number | null) {
  const qc = useQueryClient();
  const { base, coleccion } = RUTA[tab];

  // Schema propio y no el de imputación: un ajuste NO emite documento, así que su respuesta no
  // trae las claves `documento_*`. Con el schema compartido, declararlas requeridas rompería esto.
  return useMutation<AjusteResponse, Error, AjustePayload>({
    mutationFn: (payload) =>
      apiPost(`${base}/${coleccion}/${cuentaId}/ajustes`, payload, ajusteResponseSchema),
    // Sin retry: los 422 de acá son de negocio ("ese movimiento ya fue revertido") y los tiene que
    // leer la persona. Reintentar una reversa a ciegas es justo lo que el índice único previene.
    retry: false,
    onSuccess: () => {
      // Mismo alcance que `useImputar`: un ajuste mueve el saldo, no toca comprobantes ni stock.
      void qc.invalidateQueries({ queryKey: ["cuenta-corriente"] });
      void qc.invalidateQueries({ queryKey: ["dashboard"] });
    },
  });
}
