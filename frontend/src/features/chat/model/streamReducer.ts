import type { Message } from "@/entities/message/types";

import type { StreamEvent } from "./events";

export interface ChatState {
  messages: Message[];
  status: "idle" | "streaming";
  /** fase actual del backend mientras streamea ("generando" / "redactando"), o null. */
  fase: string | null;
}

/**
 * Núcleo del streaming: función PURA (estado, evento) → estado. Sin red, sin browser.
 * Aplica el evento al mensaje del asistente identificado por `assistantId`. Testeable en frío.
 */
export function reduceStream(
  state: ChatState,
  assistantId: string,
  ev: StreamEvent,
): ChatState {
  const patch = (fn: (m: Message) => Message): ChatState => ({
    ...state,
    messages: state.messages.map((m) => (m.id === assistantId ? fn(m) : m)),
  });

  switch (ev.type) {
    case "progreso":
      return { ...state, fase: ev.fase };
    case "token":
      return patch((m) => ({ ...m, content: m.content + ev.texto }));
    case "resultado":
      return patch((m) => ({ ...m, result: { sql: ev.sql, filas: ev.filas } }));
    case "bloqueado":
      return {
        ...patch((m) => ({ ...m, content: ev.answer, blocked: true, streaming: false })),
        fase: null,
      };
    case "error":
      return {
        ...patch((m) => ({ ...m, content: ev.mensaje, error: true, streaming: false })),
        fase: null,
      };
    case "fin":
      return {
        ...patch((m) => ({ ...m, streaming: false })),
        status: "idle",
        fase: null,
      };
  }
}
