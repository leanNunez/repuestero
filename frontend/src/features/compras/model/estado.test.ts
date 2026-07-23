import { describe, expect, it } from "vitest";

import {
  ESTADO_INICIAL,
  puedeEmitir,
  reducer,
  renglonValido,
  totales,
  type Estado,
  type RenglonCompra,
} from "./estado";

function renglon(over: Partial<RenglonCompra> = {}): RenglonCompra {
  return {
    articulo_codigo: "BUJIA-1",
    detalle: "BUJIA NGK",
    cantidad: "2",
    costo_unitario: "100",
    alicuota_iva: 21,
    ...over,
  };
}

function armada(over: Partial<Estado> = {}, r = renglon()): Estado {
  return {
    ...ESTADO_INICIAL,
    proveedorCodigo: "PROV-1",
    numeroComprobante: "A-0001",
    renglones: [r],
    ...over,
  };
}

describe("renglonValido", () => {
  it("acepta cantidad positiva y costo no negativo", () => {
    expect(renglonValido(renglon())).toBe(true);
    expect(renglonValido(renglon({ costo_unitario: "0" }))).toBe(true);
  });

  it("rechaza cantidad no positiva o costo vacío", () => {
    expect(renglonValido(renglon({ cantidad: "0" }))).toBe(false);
    expect(renglonValido(renglon({ cantidad: "-1" }))).toBe(false);
    expect(renglonValido(renglon({ costo_unitario: "" }))).toBe(false);
  });
});

describe("puedeEmitir", () => {
  it("necesita proveedor, número, depósito y un renglón válido", () => {
    expect(puedeEmitir(armada())).toBe(true);
  });

  it("no emite sin proveedor", () => {
    expect(puedeEmitir(armada({ proveedorCodigo: "" }))).toBe(false);
  });

  it("no emite sin número de comprobante", () => {
    expect(puedeEmitir(armada({ numeroComprobante: "  " }))).toBe(false);
  });

  it("no emite sin renglones", () => {
    expect(puedeEmitir(armada({ renglones: [] }))).toBe(false);
  });

  it("no emite si el depósito está vacío", () => {
    expect(puedeEmitir(armada({ deposito: "  " }))).toBe(false);
  });

  it("no emite si algún renglón es inválido", () => {
    expect(puedeEmitir(armada({}, renglon({ costo_unitario: "" })))).toBe(false);
  });
});

describe("totales", () => {
  it("suma neto e IVA por renglón", () => {
    const t = totales([renglon({ cantidad: "2", costo_unitario: "100", alicuota_iva: 21 })]);
    expect(t.neto).toBe(200);
    expect(t.iva).toBeCloseTo(42);
    expect(t.total).toBeCloseTo(242);
  });

  it("ignora renglones sin costo cargado todavía", () => {
    expect(totales([renglon({ costo_unitario: "" })]).total).toBe(0);
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
    const editado = reducer(dos, { type: "renglon", i: 1, campo: "costo_unitario", valor: "5" });
    expect(editado.renglones[1].costo_unitario).toBe("5");
    expect(editado.renglones[0].costo_unitario).toBe("100");
  });

  it("guarda el número de comprobante", () => {
    const s = reducer(ESTADO_INICIAL, { type: "numero", valor: "B-9" });
    expect(s.numeroComprobante).toBe("B-9");
  });

  it("reset vuelve al estado inicial", () => {
    expect(reducer(armada({ condicion: "cta_cte" }), { type: "reset" })).toEqual(ESTADO_INICIAL);
  });
});
