import { describe, expect, it } from "vitest";

import type { Movimiento } from "@/entities/cuenta-corriente/schema";

import {
  agregarForma,
  BUSQUEDA_INICIAL,
  buscar,
  cambiarForma,
  cambiarMontoForma,
  cambiarSolapa,
  espejoDelMovimiento,
  etiquetaForma,
  etiquetaTipo,
  excedeLimite,
  formasCierran,
  formasIniciales,
  montoValido,
  motivoValido,
  parseBusqueda,
  quitarForma,
  seleccionar,
  signoSaldo,
  totalFormas,
  verTodos,
  type Busqueda,
  type FormaPagoRenglon,
} from "./estado";

function busqueda(over: Partial<Busqueda> = {}): Busqueda {
  return { ...BUSQUEDA_INICIAL, ...over };
}

function mov(over: Partial<Movimiento> = {}): Movimiento {
  return {
    id: 1,
    fecha: "2026-03-20",
    tipo: "cobranza",
    debe: "0.00",
    haber: "300.00",
    ref_tipo: null,
    ref_id: null,
    motivo: null,
    anulado: false,
    reversible: true,
    anulable: false,
    creado_en: "2026-03-20T14:32:00Z",
    saldo_acumulado: "700.00",
    ...over,
  };
}

describe("parseBusqueda", () => {
  it("deja pasar una búsqueda completa y válida", () => {
    expect(
      parseBusqueda({ tab: "proveedores", q: "bosch", page: "3", sel: "12", mpage: "2", todos: "true" }),
    ).toEqual({ tab: "proveedores", q: "bosch", page: 3, sel: 12, mpage: 2, todos: true });
  });

  it("cae al default con una URL vacía", () => {
    expect(parseBusqueda({})).toEqual(BUSQUEDA_INICIAL);
  });

  it("una solapa que no existe cae a clientes", () => {
    expect(parseBusqueda({ tab: "caja" }).tab).toBe("clientes");
    expect(parseBusqueda({ tab: 42 }).tab).toBe("clientes");
  });

  it("una página inválida cae a 1", () => {
    for (const page of ["0", "-3", "abc", "1.5", "", null]) {
      expect(parseBusqueda({ page }).page).toBe(1);
    }
  });

  it("una cuenta seleccionada que no es un id cae a null", () => {
    expect(parseBusqueda({ sel: "abc" }).sel).toBeNull();
    expect(parseBusqueda({ sel: "0" }).sel).toBeNull();
    expect(parseBusqueda({ sel: "-1" }).sel).toBeNull();
    expect(parseBusqueda({ sel: "12" }).sel).toBe(12);
  });

  it("acepta `todos` como booleano o como string de la URL", () => {
    expect(parseBusqueda({ todos: true }).todos).toBe(true);
    expect(parseBusqueda({ todos: "true" }).todos).toBe(true);
    expect(parseBusqueda({ todos: "false" }).todos).toBe(false);
    expect(parseBusqueda({}).todos).toBe(false);
  });
});

describe("cambiarSolapa", () => {
  it("limpia la cuenta seleccionada", () => {
    // Sin esto, ?tab=proveedores&sel=<id de cliente> puede acertarle a un proveedor que existe
    // y mostrar la cuenta equivocada sin ningún error.
    const antes = busqueda({ sel: 7, q: "lopez", page: 4, mpage: 3 });
    expect(cambiarSolapa(antes, "proveedores")).toEqual({
      tab: "proveedores",
      q: "",
      page: 1,
      sel: null,
      mpage: 1,
      todos: false,
    });
  });

  it("conserva el filtro de cuentas en cero", () => {
    expect(cambiarSolapa(busqueda({ todos: true }), "proveedores").todos).toBe(true);
  });
});

describe("seleccionar", () => {
  it("abre el extracto en la primera página sin perder el lugar del listado", () => {
    const antes = busqueda({ q: "lopez", page: 3, mpage: 5 });
    expect(seleccionar(antes, 42)).toMatchObject({ sel: 42, mpage: 1, q: "lopez", page: 3 });
  });
});

describe("buscar", () => {
  it("vuelve al principio y cierra el detalle", () => {
    const antes = busqueda({ page: 4, sel: 9, mpage: 2 });
    expect(buscar(antes, "alsina")).toMatchObject({ q: "alsina", page: 1, sel: null, mpage: 1 });
  });
});

describe("verTodos", () => {
  it("resetea la página pero no cierra el detalle", () => {
    const antes = busqueda({ page: 5, sel: 3 });
    expect(verTodos(antes, true)).toMatchObject({ todos: true, page: 1, sel: 3 });
  });
});

describe("montoValido", () => {
  it("acepta montos positivos con punto decimal", () => {
    expect(montoValido("10.50")).toBe(true);
    expect(montoValido("1")).toBe(true);
    expect(montoValido(" 250 ")).toBe(true);
  });

  it("rechaza vacío, cero y negativos", () => {
    for (const monto of ["", "   ", "0", "0.00", "-5"]) {
      expect(montoValido(monto)).toBe(false);
    }
  });

  it("rechaza la coma decimal", () => {
    // Number("10,50") es NaN: si pasara, el backend recibiría basura. El operador argentino
    // va a tipear coma, así que la pantalla tiene que avisarle con un hint.
    expect(montoValido("10,50")).toBe(false);
  });

  it("rechaza texto", () => {
    expect(montoValido("abc")).toBe(false);
    expect(montoValido("10 pesos")).toBe(false);
  });
});

describe("etiquetaTipo", () => {
  it("traduce los tipos de las dos cuentas corrientes", () => {
    expect(etiquetaTipo("venta")).toBe("Venta");
    expect(etiquetaTipo("nota_credito")).toBe("Nota de crédito");
    expect(etiquetaTipo("compra")).toBe("Compra");
    expect(etiquetaTipo("pago")).toBe("Pago");
  });

  it("devuelve el crudo si el tipo no lo conoce", () => {
    // El importador de Paradox puede traer tipos que este front no previó: mostrar algo feo es
    // mejor que romper el extracto.
    expect(etiquetaTipo("ajuste_manual")).toBe("ajuste_manual");
  });
});

describe("signoSaldo", () => {
  it("distingue deudor, a favor y cero", () => {
    expect(signoSaldo("1300.00")).toBe("deudor");
    expect(signoSaldo("-500.00")).toBe("a-favor");
    expect(signoSaldo("0.00")).toBe("cero");
  });
});

describe("excedeLimite", () => {
  it("marca la cuenta que se pasó del límite", () => {
    expect(excedeLimite("1500", "1000")).toBe(true);
  });

  it("no marca si está justo en el límite o por debajo", () => {
    expect(excedeLimite("1000", "1000")).toBe(false);
    expect(excedeLimite("999", "1000")).toBe(false);
  });

  it("un límite en cero significa sin límite fijado, no límite cero", () => {
    expect(excedeLimite("99999", "0")).toBe(false);
  });

  it("los proveedores no tienen límite", () => {
    expect(excedeLimite("99999", null)).toBe(false);
  });
});

describe("motivoValido", () => {
  it("exige un motivo escrito de verdad", () => {
    expect(motivoValido("cobranza cargada dos veces")).toBe(true);
    expect(motivoValido("dup")).toBe(true); // el mínimo del backend son 3 caracteres
  });

  it("rechaza el vacío y los espacios", () => {
    // El backend hace strip antes de validar el min_length, así que "  " no pasa allá tampoco.
    expect(motivoValido("")).toBe(false);
    expect(motivoValido("     ")).toBe(false);
    expect(motivoValido("no")).toBe(false);
  });
});

// No hay tests de "qué se puede revertir" acá a propósito: esa regla vive en los services de
// Python y viaja resuelta en `movimiento.reversible`. Está testeada en tests/test_cta_cte.py.

describe("espejoDelMovimiento", () => {
  it("un haber se revierte con un debe del mismo importe", () => {
    expect(espejoDelMovimiento(mov({ debe: "0.00", haber: "300.00" }))).toEqual({
      columna: "Debe",
      importe: "300.00",
    });
  });

  it("un debe se revierte con un haber del mismo importe", () => {
    expect(espejoDelMovimiento(mov({ debe: "1234.56", haber: "0.00" }))).toEqual({
      columna: "Haber",
      importe: "1234.56",
    });
  });
});

// ------------------------------------------------------------------------------ formas de pago

const ren = (forma: string, monto: string) => ({ forma, monto }) as FormaPagoRenglon;

describe("totalFormas", () => {
  it("suma en centavos ENTEROS, sin el error de los floats", () => {
    // 0.1 + 0.2 === 0.30000000000000004 en float. Acá tiene que dar 30 centavos exactos.
    expect(totalFormas([ren("efectivo", "0.10"), ren("cheque", "0.20")])).toBe(30);
  });

  it("un renglón vacío o basura cuenta como cero, no rompe", () => {
    expect(totalFormas([ren("efectivo", ""), ren("cheque", "100")])).toBe(10000);
  });

  it("una lista vacía suma cero", () => {
    expect(totalFormas([])).toBe(0);
  });
});

describe("formasCierran", () => {
  it("cierra cuando los renglones suman exacto", () => {
    expect(formasCierran([ren("efectivo", "5000"), ren("cheque", "15000")], "20000")).toBe(true);
  });

  it("NO cierra por un centavo de diferencia", () => {
    // El backend devuelve 422 y la base lo rechaza con su trigger: mejor no dejar mandar.
    expect(formasCierran([ren("efectivo", "999.99")], "1000")).toBe(false);
  });

  it("no cierra con la lista vacía: un documento sin detalle no lo acepta la base", () => {
    expect(formasCierran([], "1000")).toBe(false);
  });

  it("no cierra si algún renglón está vacío o en cero", () => {
    expect(formasCierran([ren("efectivo", "1000"), ren("cheque", "")], "1000")).toBe(false);
    expect(formasCierran([ren("efectivo", "1000"), ren("cheque", "0")], "1000")).toBe(false);
  });

  it("no cierra si el monto de arriba todavía no es válido", () => {
    expect(formasCierran([ren("efectivo", "100")], "")).toBe(false);
  });

  it("maneja centavos sin perderlos", () => {
    expect(formasCierran([ren("efectivo", "1234.56")], "1234.56")).toBe(true);
    expect(formasCierran([ren("efectivo", "0.10"), ren("tarjeta", "0.20")], "0.30")).toBe(true);
  });
});

describe("formasIniciales", () => {
  it("arranca en efectivo, como el default del backend", () => {
    expect(formasIniciales("500")).toEqual([{ forma: "efectivo", monto: "500" }]);
  });
});

describe("agregarForma", () => {
  it("el renglón nuevo trae el remanente ya puesto", () => {
    // El caso real: "de los 20.000, 5.000 en efectivo y el resto un cheque".
    const r = agregarForma([ren("efectivo", "5000")], "20000");

    expect(r).toHaveLength(2);
    expect(r[1].monto).toBe("15000.00");
  });

  it("si no falta nada, el nuevo entra en cero y bloquea el submit", () => {
    const r = agregarForma([ren("efectivo", "1000")], "1000");

    expect(r[1].monto).toBe("0");
    expect(formasCierran(r, "1000")).toBe(false);
  });

  it("no rompe cuando el monto todavía está vacío", () => {
    expect(agregarForma([ren("efectivo", "")], "")).toHaveLength(2);
  });
});

describe("quitarForma", () => {
  it("saca el renglón indicado", () => {
    const r = quitarForma([ren("efectivo", "10"), ren("cheque", "20")], 0);
    expect(r).toEqual([{ forma: "cheque", monto: "20" }]);
  });

  it("NUNCA deja la lista vacía", () => {
    // Un documento sin detalle no lo acepta la base: el trigger de la 0010 lo rechaza en el commit.
    expect(quitarForma([ren("efectivo", "10")], 0)).toHaveLength(1);
  });
});

describe("cambiarForma / cambiarMontoForma", () => {
  it("cambian solo el renglón indicado", () => {
    const base = [ren("efectivo", "10"), ren("cheque", "20")];

    expect(cambiarForma(base, 1, "tarjeta")[1].forma).toBe("tarjeta");
    expect(cambiarForma(base, 1, "tarjeta")[0].forma).toBe("efectivo");
    expect(cambiarMontoForma(base, 0, "99")[0].monto).toBe("99");
    expect(cambiarMontoForma(base, 0, "99")[1].monto).toBe("20");
  });

  it("no mutan el array original", () => {
    const base = [ren("efectivo", "10")];
    cambiarMontoForma(base, 0, "999");
    expect(base[0].monto).toBe("10");
  });
});

describe("etiquetaForma", () => {
  it("traduce las formas conocidas", () => {
    expect(etiquetaForma("efectivo")).toBe("Efectivo");
    expect(etiquetaForma("transferencia")).toBe("Transferencia");
  });

  it("una forma desconocida devuelve el crudo, como etiquetaTipo", () => {
    // Mismo criterio: el importador de Paradox puede traer algo que este front no conoce.
    expect(etiquetaForma("cripto")).toBe("cripto");
  });
});
