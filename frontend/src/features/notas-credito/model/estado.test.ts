import { describe, expect, it } from "vitest";

import type { RenglonAcreditable } from "@/entities/nota-credito/schema";

import {
  aRenglonesPayload,
  desdeAcreditables,
  ESTADO_INICIAL,
  puedeEmitir,
  reducer,
  renglonValido,
  totales,
  type RenglonNC,
} from "./estado";

function renglon(over: Partial<RenglonNC> = {}): RenglonNC {
  return {
    articulo_codigo: "BUJIA-1",
    descripcion: "BUJIA NGK",
    precio_unitario: "100",
    alicuota_iva: 21,
    cantidad_acreditable: "5",
    cantidad_acreditar: "5",
    ...over,
  };
}

function acreditable(over: Partial<RenglonAcreditable> = {}): RenglonAcreditable {
  return {
    articulo_id: 1,
    articulo_codigo: "BUJIA-1",
    descripcion: "BUJIA NGK",
    precio_unitario: "100",
    alicuota_iva: "21.00",
    cantidad_vendida: "5",
    cantidad_acreditable: "5",
    ...over,
  };
}

describe("desdeAcreditables", () => {
  it("arranca cada renglón en su máximo (total por defecto)", () => {
    const [r] = desdeAcreditables([acreditable()]);
    expect(r.cantidad_acreditar).toBe("5");
    expect(r.cantidad_acreditable).toBe("5");
  });

  it("omite los renglones ya totalmente acreditados", () => {
    const renglones = desdeAcreditables([
      acreditable({ articulo_codigo: "A", cantidad_acreditable: "0" }),
      acreditable({ articulo_codigo: "B", cantidad_acreditable: "3" }),
    ]);
    expect(renglones).toHaveLength(1);
    expect(renglones[0].articulo_codigo).toBe("B");
  });
});

describe("renglonValido", () => {
  it("acepta una cantidad entre 0 y el máximo", () => {
    expect(renglonValido(renglon({ cantidad_acreditar: "3" }))).toBe(true);
    expect(renglonValido(renglon({ cantidad_acreditar: "0" }))).toBe(true);
    expect(renglonValido(renglon({ cantidad_acreditar: "5" }))).toBe(true);
  });

  it("rechaza pasarse del máximo, negativos o vacío", () => {
    expect(renglonValido(renglon({ cantidad_acreditar: "6" }))).toBe(false);
    expect(renglonValido(renglon({ cantidad_acreditar: "-1" }))).toBe(false);
    expect(renglonValido(renglon({ cantidad_acreditar: "" }))).toBe(false);
  });
});

describe("puedeEmitir", () => {
  it("necesita al menos un renglón con cantidad > 0", () => {
    expect(puedeEmitir({ renglones: [renglon({ cantidad_acreditar: "2" })] })).toBe(true);
  });

  it("no emite sin renglones", () => {
    expect(puedeEmitir(ESTADO_INICIAL)).toBe(false);
  });

  it("no emite si todo está en 0", () => {
    expect(puedeEmitir({ renglones: [renglon({ cantidad_acreditar: "0" })] })).toBe(false);
  });

  it("no emite si algún renglón se pasa del máximo", () => {
    expect(
      puedeEmitir({
        renglones: [renglon({ cantidad_acreditar: "2" }), renglon({ cantidad_acreditar: "9" })],
      }),
    ).toBe(false);
  });
});

describe("totales", () => {
  it("suma neto e IVA de lo que se acredita", () => {
    const t = totales([renglon({ cantidad_acreditar: "2", precio_unitario: "100" })]);
    expect(t.neto).toBe(200);
    expect(t.iva).toBeCloseTo(42);
    expect(t.total).toBeCloseTo(242);
  });

  it("ignora renglones en 0", () => {
    expect(totales([renglon({ cantidad_acreditar: "0" })]).total).toBe(0);
  });
});

describe("aRenglonesPayload", () => {
  it("manda solo los renglones que acreditan algo", () => {
    const payload = aRenglonesPayload({
      renglones: [
        renglon({ articulo_codigo: "A", cantidad_acreditar: "2" }),
        renglon({ articulo_codigo: "B", cantidad_acreditar: "0" }),
      ],
    });
    expect(payload).toEqual([{ articulo_codigo: "A", cantidad: "2" }]);
  });
});

describe("reducer", () => {
  it("init carga los renglones", () => {
    const s = reducer(ESTADO_INICIAL, { type: "init", renglones: [renglon()] });
    expect(s.renglones).toHaveLength(1);
  });

  it("edita la cantidad de un renglón sin tocar los demás", () => {
    const dos = {
      renglones: [renglon({ articulo_codigo: "A" }), renglon({ articulo_codigo: "B" })],
    };
    const editado = reducer(dos, { type: "cantidad", i: 1, valor: "3" });
    expect(editado.renglones[1].cantidad_acreditar).toBe("3");
    expect(editado.renglones[0].cantidad_acreditar).toBe("5");
  });

  it("reset vuelve al estado inicial", () => {
    expect(reducer({ renglones: [renglon()] }, { type: "reset" })).toEqual(ESTADO_INICIAL);
  });
});
