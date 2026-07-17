import { useMutation, useQueryClient } from "@tanstack/react-query";

import {
  confirmarResponseSchema,
  propuestaSchema,
  type ConfirmarResponse,
  type Propuesta,
} from "@/entities/remito/schema";
import { apiPost } from "@/shared/api/client";

import type { Estado } from "./estado";

export function useExtraerRemito() {
  return useMutation<Propuesta, Error, { imagen_base64: string; mime: string }>({
    mutationFn: (body) => apiPost("/ingesta-visual/extraer", body, propuestaSchema),
    // Sin retry: cada intento cuesta tokens de visión. Si falló, que lo decida la persona.
    retry: false,
  });
}

/** Arma el payload de confirmación desde lo que el humano dejó en pantalla.
 *
 * Solo entran los renglones tildados, y con los valores EDITADOS — no con los que leyó Repu.
 * Los importes van como string, tal como llegaron: nunca pasan por Number. */
function aPayload(estado: Estado) {
  return {
    remito_hash: estado.propuesta?.remito_hash ?? "",
    numero_remito: estado.numeroRemito.trim() || null,
    fecha: estado.propuesta?.fecha ?? null,
    total_declarado: estado.propuesta?.total_declarado ?? null,
    proveedor_codigo: estado.proveedorCodigo.trim() || null,
    proveedor_razon_social: estado.propuesta?.proveedor_nombre ?? null,
    proveedor_cuit: estado.propuesta?.proveedor_cuit ?? null,
    deposito_codigo: estado.deposito.trim(),
    renglones: estado.renglones
      .filter((r) => r.incluir)
      .map((r) => ({
        codigo: r.codigo_editado.trim(),
        detalle: r.detalle_editado.trim(),
        cantidad: r.cantidad_editada,
        costo_unitario: r.costo_editado,
        codigo_proveedor: r.codigo?.trim() || null,
      })),
  };
}

export function useConfirmarRemito() {
  const qc = useQueryClient();

  return useMutation<ConfirmarResponse, Error, Estado>({
    mutationFn: (estado) =>
      apiPost("/ingesta-visual/confirmar", aPayload(estado), confirmarResponseSchema),
    retry: false,
    onSuccess: () => {
      // El remito cambió costos, stock y precios: lo que está en pantalla quedó viejo.
      void qc.invalidateQueries({ queryKey: ["catalogo"] });
      void qc.invalidateQueries({ queryKey: ["articulo"] });
      void qc.invalidateQueries({ queryKey: ["dashboard"] });
    },
  });
}
