import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import type { Movimiento } from "@/entities/cuenta-corriente/schema";

import { ExtractoTable } from "./ExtractoTable";

function mov(over: Partial<Movimiento> = {}): Movimiento {
  return {
    id: 1,
    fecha: "2026-03-20",
    tipo: "venta",
    debe: "500.00",
    haber: "0.00",
    ref_tipo: "comprobante",
    ref_id: 123,
    motivo: null,
    anulado: false,
    // Una venta no es reversible; el backend lo resuelve y la tabla solo lee este flag.
    reversible: false,
    saldo_acumulado: "1200.00",
    ...over,
  };
}

function pintar(movimientos: Movimiento[] | undefined, over = {}) {
  return render(
    <ExtractoTable
      movimientos={movimientos}
      isLoading={false}
      isError={false}
      onRetry={vi.fn()}
      onRevertir={vi.fn()}
      {...over}
    />,
  );
}

describe("ExtractoTable", () => {
  it("pinta un movimiento con sus columnas", () => {
    pintar([mov()]);

    const fila = screen.getAllByRole("row")[1];
    expect(fila).toBeDefined();
    expect(within(fila!).getByText("20/03/2026")).toBeInTheDocument();
    expect(within(fila!).getByText("Venta")).toBeInTheDocument();
    expect(within(fila!).getByText("Comprobante #123")).toBeInTheDocument();
  });

  it("muestra el saldo acumulado que vino del backend, sin recalcularlo", () => {
    // La tabla solo tiene una página: si intentara sumar debe/haber por su cuenta, el acumulado
    // de la primera fila estaría mal en cualquier página que no sea la primera.
    pintar([mov({ debe: "500.00", saldo_acumulado: "99999.00" })]);
    expect(screen.getByText(/99\.999/)).toBeInTheDocument();
  });

  it("deja en guión la columna que no aplica", () => {
    pintar([mov({ debe: "0.00", haber: "300.00", tipo: "cobranza" })]);

    const fila = screen.getAllByRole("row")[1];
    expect(within(fila!).getAllByText("—")).toHaveLength(1); // solo Debe
  });

  it("no rompe con un movimiento sin referencia", () => {
    // Las cobranzas y pagos llegan sin ref_tipo/ref_id: el service no las guarda todavía.
    pintar([mov({ tipo: "cobranza", ref_tipo: null, ref_id: null, debe: "0.00", haber: "300.00" })]);

    const fila = screen.getAllByRole("row")[1];
    expect(within(fila!).getAllByText("—")).toHaveLength(2); // Debe y Referencia
  });

  it("muestra el tipo crudo si no lo conoce", () => {
    pintar([mov({ tipo: "ajuste_migracion" })]);
    expect(screen.getByText("ajuste_migracion")).toBeInTheDocument();
  });

  it("muestra el estado vacío sin movimientos", () => {
    pintar([]);
    expect(screen.getByText("Esta cuenta no tiene movimientos")).toBeInTheDocument();
    expect(screen.queryByRole("table")).toBeNull();
  });

  it("muestra el error con reintento", () => {
    const onRetry = vi.fn();
    pintar(undefined, { isError: true, onRetry });
    expect(screen.getByRole("button", { name: "Reintentar" })).toBeInTheDocument();
  });

  it("las columnas están rotuladas para lectores de pantalla", () => {
    pintar([mov()]);
    const encabezados = screen.getAllByRole("columnheader");
    expect(encabezados.map((h) => h.textContent)).toEqual([
      "Fecha",
      "Concepto",
      "Referencia",
      "Debe",
      "Haber",
      "Saldo",
      "Acciones",
    ]);
  });

  describe("revertir", () => {
    // La tabla NO decide qué se puede revertir: lee `reversible`, que ya viene resuelto por el
    // backend (ver MOVIMIENTOS_REVERSIBLES en los services). Acá solo se prueba que lo obedezca.

    it("ofrece revertir lo que el backend marcó reversible, y avisa cuál es", async () => {
      const onRevertir = vi.fn();
      const cobranza = mov({
        id: 7,
        tipo: "cobranza",
        debe: "0.00",
        haber: "300.00",
        reversible: true,
      });
      pintar([cobranza], { onRevertir });

      const boton = screen.getByRole("button", { name: /Revertir cobranza del 20\/03\/2026/ });
      await userEvent.click(boton);

      expect(onRevertir).toHaveBeenCalledWith(cobranza);
    });

    it("no ofrece el botón cuando el backend dice que no", () => {
      // Es el caso de una venta: espeja un comprobante y se corrige con una nota de crédito.
      pintar([mov({ tipo: "venta", reversible: false })]);
      expect(screen.queryByRole("button", { name: /Revertir/ })).toBeNull();
    });

    it("un movimiento anulado muestra el estado en vez del botón", () => {
      // El backend manda `reversible: false` en los anulados: revertir dos veces duplicaría la
      // corrección, y el índice único de la base lo rechazaría igual.
      pintar([
        mov({ tipo: "cobranza", debe: "0.00", haber: "300.00", anulado: true, reversible: false }),
      ]);

      expect(screen.getByText("Anulado")).toBeInTheDocument();
      expect(screen.queryByRole("button", { name: /Revertir/ })).toBeNull();
    });

    it("funciona igual en proveedores: el flag no depende de la solapa", () => {
      pintar([mov({ tipo: "pago", debe: "0.00", haber: "300.00", reversible: true })]);
      expect(screen.getByRole("button", { name: /Revertir pago/ })).toBeInTheDocument();
    });

    it("muestra el motivo del ajuste debajo del concepto", () => {
      pintar([mov({ tipo: "ajuste", motivo: "cobranza cargada dos veces" })]);
      expect(screen.getByText("cobranza cargada dos veces")).toBeInTheDocument();
    });
  });
});
