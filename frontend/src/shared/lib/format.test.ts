import { describe, expect, it } from "vitest";

import { fechaCorta, iniciales } from "./format";

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

describe("iniciales", () => {
  it("toma las dos primeras palabras", () => {
    expect(iniciales("Taller Mecánico El Rulo")).toBe("TM");
  });

  it("saltea los conectores", () => {
    // "Juntas y Retenes del Norte SRL" daba "JY", que no identifica a nadie. En razones sociales
    // los conectores aparecen todo el tiempo.
    expect(iniciales("Juntas y Retenes del Norte SRL")).toBe("JR");
    expect(iniciales("Embragues y Transmisiones SA")).toBe("ET");
    expect(iniciales("Dirección y Tren Delantero SA")).toBe("DT");
  });

  it("un nombre de una sola palabra da una sola inicial", () => {
    expect(iniciales("Bulonera")).toBe("B");
  });

  it("un nombre que es puro conector no se queda sin avatar", () => {
    // Preferible una inicial pobre a un "?" sobre un nombre que existe.
    expect(iniciales("La Y")).toBe("LY");
  });

  it("un nombre vacío no rompe la fila", () => {
    expect(iniciales("   ")).toBe("?");
  });
});
