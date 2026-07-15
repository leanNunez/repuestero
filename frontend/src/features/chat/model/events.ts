import { z } from "zod";

import type { Row } from "@/entities/message/types";

/** Schemas de los payloads SSE del backend (validación en el boundary — no confiar en la red). */
const progresoSchema = z.object({ fase: z.string() });
const tokenSchema = z.object({ texto: z.string() });
const resultadoSchema = z.object({
  sql: z.string().nullable(),
  filas: z.array(z.record(z.string(), z.unknown())),
});
const bloqueadoSchema = z.object({ answer: z.string() });
const errorSchema = z.object({ mensaje: z.string() });

/** Evento ya parseado y validado, listo para el reducer. */
export type StreamEvent =
  | { type: "progreso"; fase: string }
  | { type: "token"; texto: string }
  | { type: "resultado"; sql: string | null; filas: Row[] }
  | { type: "bloqueado"; answer: string }
  | { type: "error"; mensaje: string }
  | { type: "fin" };

/**
 * Mapea un mensaje SSE crudo (nombre de evento + data JSON) a un StreamEvent validado.
 * Devuelve null para eventos desconocidos. Lanza si el JSON o el schema no validan (el caller decide).
 */
export function parseSSE(eventName: string, data: string): StreamEvent | null {
  const json: unknown = data ? JSON.parse(data) : {};
  switch (eventName) {
    case "progreso":
      return { type: "progreso", ...progresoSchema.parse(json) };
    case "token":
      return { type: "token", ...tokenSchema.parse(json) };
    case "resultado": {
      const r = resultadoSchema.parse(json);
      return { type: "resultado", sql: r.sql, filas: r.filas };
    }
    case "bloqueado":
      return { type: "bloqueado", ...bloqueadoSchema.parse(json) };
    case "error":
      return { type: "error", ...errorSchema.parse(json) };
    case "fin":
      return { type: "fin" };
    default:
      return null;
  }
}
