import { describe, expect, it } from "vitest";

import type { Message } from "@/entities/message/types";

import { reduceStream, type ChatState } from "./streamReducer";

function baseState(): ChatState {
  const user: Message = { id: "u1", role: "user", content: "hola", streaming: false };
  const assistant: Message = { id: "a1", role: "assistant", content: "", streaming: true };
  return { messages: [user, assistant], status: "streaming", fase: null };
}

describe("reduceStream", () => {
  it("construye el mensaje con progreso → token×N → resultado → fin", () => {
    let s = baseState();
    s = reduceStream(s, "a1", { type: "progreso", fase: "generando" });
    expect(s.fase).toBe("generando");

    s = reduceStream(s, "a1", { type: "token", texto: "Hola " });
    s = reduceStream(s, "a1", { type: "token", texto: "mundo" });
    s = reduceStream(s, "a1", { type: "resultado", sql: "SELECT 1", filas: [{ n: 1 }] });
    s = reduceStream(s, "a1", { type: "fin" });

    const a = s.messages.find((m) => m.id === "a1")!;
    expect(a.content).toBe("Hola mundo");
    expect(a.result).toEqual({ sql: "SELECT 1", filas: [{ n: 1 }] });
    expect(a.streaming).toBe(false);
    expect(s.status).toBe("idle");
    expect(s.fase).toBeNull();
  });

  it("bloqueado marca el mensaje y corta el streaming", () => {
    const s = reduceStream(baseState(), "a1", {
      type: "bloqueado",
      answer: "No puedo procesar eso.",
    });
    const a = s.messages.find((m) => m.id === "a1")!;
    expect(a.blocked).toBe(true);
    expect(a.content).toBe("No puedo procesar eso.");
    expect(a.streaming).toBe(false);
  });

  it("error marca el mensaje con error y corta el streaming", () => {
    const s = reduceStream(baseState(), "a1", { type: "error", mensaje: "falló" });
    const a = s.messages.find((m) => m.id === "a1")!;
    expect(a.error).toBe(true);
    expect(a.streaming).toBe(false);
  });

  it("no toca otros mensajes al aplicar un token", () => {
    const s = reduceStream(baseState(), "a1", { type: "token", texto: "x" });
    expect(s.messages.find((m) => m.id === "u1")!.content).toBe("hola");
  });
});
