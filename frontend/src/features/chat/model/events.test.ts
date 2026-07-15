import { describe, expect, it } from "vitest";

import { parseSSE } from "./events";

describe("parseSSE", () => {
  it("parsea token, resultado y fin", () => {
    expect(parseSSE("token", JSON.stringify({ texto: "hi" }))).toEqual({
      type: "token",
      texto: "hi",
    });
    expect(parseSSE("resultado", JSON.stringify({ sql: "S", filas: [] }))).toEqual({
      type: "resultado",
      sql: "S",
      filas: [],
    });
    expect(parseSSE("fin", "{}")).toEqual({ type: "fin" });
  });

  it("devuelve null para eventos desconocidos", () => {
    expect(parseSSE("otro", "{}")).toBeNull();
  });

  it("lanza si el payload no valida el schema (boundary Zod)", () => {
    expect(() => parseSSE("token", JSON.stringify({ nope: 1 }))).toThrow();
  });
});
