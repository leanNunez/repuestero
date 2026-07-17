import { fetchEventSource } from "@microsoft/fetch-event-source";

import { authHeaders, STREAM_URL } from "@/shared/api/client";

import { useChatStore } from "./chatStore";
import { parseSSE } from "./events";

/**
 * Orquesta el envío y el consumo del stream SSE. La lógica de estado vive en el reducer puro
 * (`reduceStream`); acá solo se cablea `fetchEventSource` al store.
 */
export function useChat() {
  const messages = useChatStore((s) => s.messages);
  const status = useChatStore((s) => s.status);
  const fase = useChatStore((s) => s.fase);
  const sendUser = useChatStore((s) => s.sendUser);
  const apply = useChatStore((s) => s.apply);

  const send = async (text: string) => {
    const trimmed = text.trim();
    if (!trimmed || status === "streaming") return;

    const assistantId = sendUser(trimmed);
    const ctrl = new AbortController();
    let finished = false;

    try {
      await fetchEventSource(STREAM_URL, {
        method: "POST",
        headers: authHeaders(),
        body: JSON.stringify({ message: trimmed }),
        signal: ctrl.signal,
        openWhenHidden: true,
        onopen: async (res) => {
          if (!res.ok) throw new Error(`HTTP ${res.status}`);
        },
        onmessage: (ev) => {
          try {
            const parsed = parseSSE(ev.event, ev.data);
            if (!parsed) return;
            apply(assistantId, parsed);
            if (parsed.type === "fin") {
              finished = true;
              ctrl.abort(); // cierre normal: cortar antes de que fetchEventSource reintente.
            }
          } catch {
            /* evento malformado: ignorar, no cortar el stream */
          }
        },
        onclose: () => {
          // Cierre inesperado (sin `fin`): frenar el retry automático lanzando.
          if (!finished) throw new Error("stream cerrado sin fin");
        },
        onerror: (err) => {
          throw err; // corta el retry automático de fetchEventSource
        },
      });
    } catch {
      if (finished) return; // el abort tras `fin` cae acá: es un cierre esperado.
      apply(assistantId, {
        type: "error",
        mensaje: "No pude conectar con el asistente. ¿El backend está corriendo y el token es válido?",
      });
    }
  };

  return { messages, status, fase, send };
}
