import { describe, expect, it } from "vitest";

import {
  BUSQUEDA_INICIAL,
  CONCEPTOS_MANUALES,
  avisoDeNegativo,
  cambiarSolapa,
  estaEnNegativo,
  etiquetaConcepto,
  filtrarEstado,
  filtrarForma,
  parseBusqueda,
} from "./estado";

describe("parseBusqueda", () => {
  it("una URL vacía cae en los defaults", () => {
    expect(parseBusqueda({})).toEqual(BUSQUEDA_INICIAL);
  });

  it("lee una URL válida", () => {
    expect(parseBusqueda({ tab: "cartera", estado: "depositado", cpage: "3" })).toMatchObject({
      tab: "cartera",
      estado: "depositado",
      cpage: 3,
    });
  });

  it("un filtro inventado degrada a null en vez de viajar al backend", () => {
    // Mandar `?forma=bitcoin` daría un 422 y la pantalla mostraría un error de red por algo que se
    // resuelve acá sin pedir nada.
    expect(parseBusqueda({ forma: "bitcoin" }).forma).toBeNull();
    expect(parseBusqueda({ estado: "extraviado" }).estado).toBeNull();
  });

  it("una página basura degrada a 1 y no rompe la pantalla", () => {
    for (const page of ["0", "-3", "abc", "1.5", null, undefined, {}]) {
      expect(parseBusqueda({ page }).page).toBe(1);
    }
  });

  it("una solapa inventada cae en caja", () => {
    expect(parseBusqueda({ tab: "marciano" }).tab).toBe("caja");
  });
});

describe("cambiarSolapa", () => {
  it("limpia los filtros de la solapa anterior", () => {
    // Sin esto, volver a Caja después de filtrar la cartera dejaría un filtro invisible aplicado a
    // otra cosa, y la pantalla estaría mintiendo sin decir por qué.
    const desde = { tab: "cartera" as const, forma: null, estado: "cobrado", page: 2, cpage: 4 };

    expect(cambiarSolapa(desde, "caja")).toEqual({ ...BUSQUEDA_INICIAL, tab: "caja" });
  });

  it("quedarse en la misma solapa no resetea nada de la otra", () => {
    const actual = { ...BUSQUEDA_INICIAL, tab: "caja" as const, forma: "efectivo", page: 3 };

    expect(cambiarSolapa(actual, "caja").tab).toBe("caja");
  });
});

describe("filtros", () => {
  it("filtrar por forma vuelve a la página 1", () => {
    // Si no, quedarías en la página 7 de un conjunto que ahora tiene 2 páginas: tabla vacía sin
    // explicación.
    const actual = { ...BUSQUEDA_INICIAL, page: 7 };

    expect(filtrarForma(actual, "cheque")).toMatchObject({ forma: "cheque", page: 1 });
  });

  it("filtrar por estado vuelve a la página 1 de la cartera", () => {
    const actual = { ...BUSQUEDA_INICIAL, cpage: 5 };

    expect(filtrarEstado(actual, "depositado")).toMatchObject({ estado: "depositado", cpage: 1 });
  });
});

describe("saldo en negativo", () => {
  it("detecta el negativo", () => {
    expect(estaEnNegativo("-0.01")).toBe(true);
    expect(estaEnNegativo("0")).toBe(false);
    expect(estaEnNegativo("1000.00")).toBe(false);
  });

  it("el aviso dice el número, no solo que hay un problema", () => {
    // Un aviso que no dice cuánto obliga a ir a buscarlo.
    expect(avisoDeNegativo("efectivo", "-8500.00")).toContain("-8500.00");
  });
});

describe("vocabulario", () => {
  it("traduce los conceptos del backend", () => {
    expect(etiquetaConcepto("cheque_cobrado_cartera")).toBe("Cheque sale de cartera");
  });

  it("un concepto desconocido se muestra legible en vez de vacío", () => {
    expect(etiquetaConcepto("algo_nuevo")).toBe("algo nuevo");
  });

  it("solo ofrece conceptos MANUALES para el alta a mano", () => {
    // La reja de verdad está en el backend (dos veces). Esto evita que la persona llegue a
    // intentar cargar a mano una cobranza que el recibo ya generó.
    const ids = CONCEPTOS_MANUALES.map((c) => c.id);

    expect(ids).not.toContain("cobranza");
    expect(ids).not.toContain("pago_proveedor");
    expect(ids).not.toContain("cheque_cobrado");
    expect(ids).toContain("gasto");
  });
});
