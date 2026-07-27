import { describe, expect, it } from "vitest";

import {
  chequePaginaSchema,
  chequeResponseSchema,
  movimientoCajaPaginaSchema,
  movimientoCajaResponseSchema,
  saldoCajaSchema,
} from "./schema";

/** Contrato contra respuestas REALES del backend, capturadas de un uvicorn corriendo.
 *
 * Los tests de componentes usan fixtures que yo mismo escribo, así que confirman que el componente
 * hace lo que digo — no que el backend devuelva lo que creo. Un schema Zod que no coincide con la
 * respuesta real no lo caza ningún test de UI: revienta en runtime, en la cara de la persona.
 *
 * Estas capturas salieron de `GET /caja/saldo`, `/caja/movimientos`, `/caja/cheques`,
 * `POST /caja/movimientos` y `POST /caja/cheques/{id}/cobrar` sobre una org sembrada con un recibo
 * mixto (5.000 efectivo + 15.000 cheque) y un gasto manual. Si el backend cambia el contrato, esto
 * se pone rojo acá y no en producción. */

/** Capturado con un recibo de 15.000 en cheque MÁS una orden de pago de 4.000 con cheque propio.
 *
 * Es el caso que SEPARA los dos números: `por_forma.cheque` = 15.000 − 4.000 = 11.000 (el neto del
 * libro, que resta el emitido) y `cheques_en_cartera` = 15.000 (lo que tengo en la mano).
 * Confundirlos era el bug: la pantalla mostraba el neto rotulado "Cheques en cartera". */
const SALDO = {
  efectivo: "5000.00",
  por_forma: {
    efectivo: "5000.00",
    cheque: "11000.00",
    transferencia: "0",
    tarjeta: "0",
  },
  cheques_en_cartera: "15000.00",
};

const MOVIMIENTOS = {
  items: [
    {
      id: 21,
      fecha: "2026-07-27",
      concepto: "gasto",
      forma: "efectivo",
      ingreso: "0.00",
      egreso: "300.00",
      detalle: "flete",
      ref_tipo: null,
      ref_id: null,
      creado_en: "2026-07-27T14:23:34.614405-03:00",
      saldo_acumulado: "4700.00",
    },
    {
      id: 20,
      fecha: "2026-07-27",
      concepto: "cobranza",
      forma: "cheque",
      ingreso: "15000.00",
      egreso: "0.00",
      detalle: null,
      ref_tipo: "recibo",
      ref_id: 1,
      creado_en: "2026-07-27T14:23:34.614405-03:00",
      saldo_acumulado: "15000.00",
    },
    {
      id: 19,
      fecha: "2026-07-27",
      concepto: "cobranza",
      forma: "efectivo",
      ingreso: "5000.00",
      egreso: "0.00",
      detalle: null,
      ref_tipo: "recibo",
      ref_id: 1,
      creado_en: "2026-07-27T14:23:34.614405-03:00",
      saldo_acumulado: "5000.00",
    },
  ],
  total: 3,
};

const CHEQUES = {
  items: [
    {
      id: 5,
      origen: "recibido",
      importe: "15000.00",
      estado: "en_cartera",
      banco: null,
      numero: null,
      fecha_emision: null,
      fecha_cobro: null,
      conciliado: false,
      fecha_conciliacion: null,
      ref_tipo: "recibo",
      ref_id: 1,
      creado_en: "2026-07-27T14:23:34.614405-03:00",
    },
  ],
  total: 1,
  valor_en_cartera: "15000.00",
};

const ALTA_CON_ADVERTENCIA = {
  movimiento_id: 22,
  concepto: "retiro",
  forma: "efectivo",
  saldo: "-995299.00",
  advertencias: [
    "El efectivo quedó en -995,299.00. Un saldo negativo no puede pasar en la realidad: revisá si falta cargar un ingreso.",
  ],
};

const COBRAR = {
  cheque: {
    id: 5,
    origen: "recibido",
    importe: "15000.00",
    estado: "cobrado",
    banco: null,
    numero: null,
    fecha_emision: null,
    fecha_cobro: null,
    conciliado: false,
    fecha_conciliacion: null,
    ref_tipo: "recibo",
    ref_id: 1,
    creado_en: "2026-07-27T14:23:34.614405-03:00",
  },
  movimientos: [
    {
      movimiento_id: 23,
      concepto: "cheque_cobrado_cartera",
      forma: "cheque",
      saldo: "0.00",
      advertencias: [],
    },
    {
      movimiento_id: 24,
      concepto: "cheque_cobrado",
      forma: "efectivo",
      saldo: "-980299.00",
      advertencias: [],
    },
  ],
  saldos: {
    transferencia: "0",
    tarjeta: "0",
    efectivo: "-980299.00",
    cheque: "0.00",
  },
};

describe("contrato con el backend", () => {
  it("GET /caja/saldo separa el neto del libro del valor de la cartera", () => {
    const s = saldoCajaSchema.parse(SALDO);

    // El invariante real, verificado contra una respuesta de verdad:
    //     por_forma.cheque  ==  cheques_en_cartera  -  (suma de los emitidos)
    expect(s.cheques_en_cartera).toBe("15000.00");
    expect(s.por_forma.cheque).toBe("11000.00");
    expect(Number(s.por_forma.cheque)).toBeLessThan(Number(s.cheques_en_cartera));
  });

  it("GET /caja/movimientos, con y sin referencia", () => {
    const p = movimientoCajaPaginaSchema.parse(MOVIMIENTOS);

    // El manual viene sin referencia y el derivado con ella: es el invariante del módulo visible
    // en el contrato.
    expect(p.items[0]?.ref_tipo).toBeNull();
    expect(p.items[1]?.ref_tipo).toBe("recibo");
  });

  it("GET /caja/cheques con los datos del papel todavía en NULL", () => {
    const p = chequePaginaSchema.parse(CHEQUES);

    expect(p.items[0]?.banco).toBeNull();
    expect(p.valor_en_cartera).toBe("15000.00");
  });

  it("POST /caja/movimientos trae las advertencias del saldo negativo", () => {
    const r = movimientoCajaResponseSchema.parse(ALTA_CON_ADVERTENCIA);

    expect(r.advertencias).toHaveLength(1);
  });

  it("POST /caja/cheques/{id}/cobrar trae las DOS patas del asiento", () => {
    const r = chequeResponseSchema.parse(COBRAR);

    // El papel sale de la cartera y la plata entra: un hecho, dos filas. Si el front solo esperara
    // una, la pantalla mostraría media operación.
    expect(r.movimientos.map((m) => m.concepto).sort()).toEqual([
      "cheque_cobrado",
      "cheque_cobrado_cartera",
    ]);
    expect(r.saldos.cheque).toBe("0.00");
  });

  it("la plata NUNCA llega como número", () => {
    // La regla no negociable del proyecto, verificada en el borde donde entra al front.
    const r = movimientoCajaPaginaSchema.parse(MOVIMIENTOS);

    for (const m of r.items) {
      expect(typeof m.ingreso).toBe("string");
      expect(typeof m.saldo_acumulado).toBe("string");
    }
  });
});
