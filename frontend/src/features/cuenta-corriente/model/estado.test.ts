import { describe, expect, it } from "vitest";

import type { Movimiento } from "@/entities/cuenta-corriente/schema";

import {
  BUSQUEDA_INICIAL,
  buscar,
  cambiarSolapa,
  espejoDelMovimiento,
  etiquetaTipo,
  excedeLimite,
  montoValido,
  motivoValido,
  parseBusqueda,
  seleccionar,
  signoSaldo,
  verTodos,
  type Busqueda,
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
