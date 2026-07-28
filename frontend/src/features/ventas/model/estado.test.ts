import { describe, expect, it } from "vitest";

import {
  ESTADO_INICIAL,
  puedeEmitir,
  reducer,
  renglonValido,
  totales,
  type Estado,
  type RenglonVenta,
} from "./estado";

function renglon(over: Partial<RenglonVenta> = {}): RenglonVenta {
  return {
    articulo_codigo: "BUJIA-1",
    detalle: "BUJIA NGK",
    cantidad: "2",
    precio_unitario: "100",
    alicuota_iva: 21,
    lista_codigo: "MOST",
    ...over,
  };
}

function conRenglon(over: Partial<Estado> = {}, r = renglon()): Estado {
  return { ...ESTADO_INICIAL, clienteCodigo: "CLI-1", renglones: [r], ...over };
}

describe("renglonValido", () => {
  it("acepta cantidad positiva y precio no negativo", () => {
    expect(renglonValido(renglon())).toBe(true);
    expect(renglonValido(renglon({ precio_unitario: "0" }))).toBe(true);
  });

  it("rechaza cantidad no positiva o precio vacío", () => {
    expect(renglonValido(renglon({ cantidad: "0" }))).toBe(false);
    expect(renglonValido(renglon({ cantidad: "-1" }))).toBe(false);
    expect(renglonValido(renglon({ precio_unitario: "" }))).toBe(false);
  });
});

describe("puedeEmitir", () => {
  it("necesita cliente, depósito y al menos un renglón válido", () => {
    expect(puedeEmitir(conRenglon())).toBe(true);
  });

  it("no emite sin cliente", () => {
    expect(puedeEmitir(conRenglon({ clienteCodigo: "" }))).toBe(false);
  });

  it("no emite sin renglones", () => {
    expect(puedeEmitir(conRenglon({ renglones: [] }))).toBe(false);
  });

  it("no emite si el depósito está vacío", () => {
    expect(puedeEmitir(conRenglon({ deposito: "  " }))).toBe(false);
  });

  it("no emite si algún renglón es inválido", () => {
    expect(puedeEmitir(conRenglon({}, renglon({ cantidad: "0" })))).toBe(false);
  });
});

describe("totales", () => {
  it("suma neto e IVA por renglón", () => {
    const t = totales([renglon({ cantidad: "2", precio_unitario: "100", alicuota_iva: 21 })]);
    expect(t.neto).toBe(200);
    expect(t.iva).toBeCloseTo(42);
    expect(t.total).toBeCloseTo(242);
  });

  it("ignora renglones sin precio cargado todavía", () => {
    const t = totales([renglon({ precio_unitario: "" })]);
    expect(t.total).toBe(0);
  });
});

describe("reducer", () => {
  it("agrega y quita renglones", () => {
    const conUno = reducer(ESTADO_INICIAL, { type: "agregar", renglon: renglon() });
    expect(conUno.renglones).toHaveLength(1);
    const vacio = reducer(conUno, { type: "quitar", i: 0 });
    expect(vacio.renglones).toHaveLength(0);
  });

  it("edita un campo de un renglón sin tocar los demás", () => {
    const dos = {
      ...ESTADO_INICIAL,
      renglones: [renglon({ articulo_codigo: "A" }), renglon({ articulo_codigo: "B" })],
    };
    const editado = reducer(dos, { type: "renglon", i: 1, campo: "cantidad", valor: "5" });
    expect(editado.renglones[1].cantidad).toBe("5");
    expect(editado.renglones[0].cantidad).toBe("2");
  });

  it("reset vuelve al estado inicial", () => {
    const sucio = conRenglon({ condicion: "cta_cte" });
    expect(reducer(sucio, { type: "reset" })).toEqual(ESTADO_INICIAL);
  });
});
