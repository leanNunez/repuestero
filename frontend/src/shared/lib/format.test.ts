import { describe, expect, it } from "vitest";

import { fechaCorta } from "./format";

describe("fechaCorta", () => {
  it("da vuelta la fecha ISO del backend", () => {
    expect(fechaCorta("2026-07-24")).toBe("24/07/2026");
  });

  it("NO corre la fecha un día para atrás", () => {
    // Este assert existe para que nadie reescriba `fechaCorta` con `new Date`:
    // `new Date("2026-01-01")` es medianoche UTC, y en Argentina (UTC-3) se renderiza como
    // 31/12/2025. Un movimiento de cuenta corriente fechado un día antes es un problema real.
    expect(fechaCorta("2026-01-01")).toBe("01/01/2026");
  });

  it("ignora la hora si el backend la mandara", () => {
    expect(fechaCorta("2026-07-24T15:30:00Z")).toBe("24/07/2026");
  });

  it("muestra un guión cuando no hay fecha", () => {
    expect(fechaCorta(null)).toBe("—");
    expect(fechaCorta(undefined)).toBe("—");
    expect(fechaCorta("")).toBe("—");
  });

  it("devuelve el crudo si no puede parsearlo", () => {
    expect(fechaCorta("ayer")).toBe("ayer");
  });
});
