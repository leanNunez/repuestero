// Verificación end-to-end del pipeline del frontend contra el backend real.
// Usa el MISMO cliente SSE (@microsoft/fetch-event-source) + parseSSE + reduceStream que la app.
// Uso: bun scripts/verify_stream.ts <JWT> ["mensaje"]

// Shim mínimo: fetch-event-source referencia window/document (API de visibilidad del navegador).
// El núcleo (fetch + parseo SSE) es agnóstico del entorno; esto solo lo deja arrancar en bun.
const g = globalThis as unknown as { window?: unknown; document?: unknown };
g.window ??= globalThis;
g.document ??= {
  addEventListener() {},
  removeEventListener() {},
  hidden: false,
  visibilityState: "visible",
};

// import dinámico DESPUÉS del shim (los import estáticos se hoistean y correrían antes del shim).
const { fetchEventSource } = await import("@microsoft/fetch-event-source");

import type { Message } from "../src/entities/message/types";
import { parseSSE } from "../src/features/chat/model/events";
import { reduceStream, type ChatState } from "../src/features/chat/model/streamReducer";

const token = process.argv[2];
const message = process.argv[3] ?? "¿cuántos artículos hay en total?";

const assistant: Message = { id: "a1", role: "assistant", content: "", streaming: true };
let state: ChatState = {
  messages: [
    { id: "u1", role: "user", content: message, streaming: false },
    assistant,
  ],
  status: "streaming",
  fase: null,
};

const secuencia: string[] = [];
const ctrl = new AbortController();
let finished = false;

await fetchEventSource("http://localhost:8000/asistente/stream", {
  method: "POST",
  headers: { "Content-Type": "application/json", Authorization: `Bearer ${token}` },
  body: JSON.stringify({ message }),
  signal: ctrl.signal,
  openWhenHidden: true,
  onopen: async (res) => {
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
  },
  onmessage: (ev) => {
    const parsed = parseSSE(ev.event, ev.data);
    if (!parsed) return;
    secuencia.push(parsed.type);
    state = reduceStream(state, "a1", parsed);
    if (parsed.type === "fin") {
      finished = true;
      ctrl.abort();
    }
  },
  onclose: () => {
    if (!finished) throw new Error("stream cerrado sin fin");
  },
  onerror: (e) => {
    throw e;
  },
}).catch((e: Error) => {
  if (!finished) {
    console.error("ERROR:", e.message);
    process.exit(1);
  }
});

const a = state.messages.find((m) => m.id === "a1")!;
console.log("secuencia :", secuencia.join(" → "));
console.log("respuesta :", JSON.stringify(a.content));
console.log("sql       :", a.result?.sql ?? "(sin resultado)");
console.log("filas     :", JSON.stringify(a.result?.filas ?? []));
console.log("streaming :", a.streaming, "| status:", state.status, "| blocked:", a.blocked ?? false);
