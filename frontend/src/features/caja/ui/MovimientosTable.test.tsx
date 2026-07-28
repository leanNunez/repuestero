import { render, screen, within } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import type { MovimientoCaja } from "@/entities/caja/schema";

import { MovimientosTable } from "./MovimientosTable";

function mov(over: Partial<MovimientoCaja> = {}): MovimientoCaja {
  return {
    id: 1,
    fecha: "2026-07-27",
    concepto: "gasto",
    forma: "efectivo",
    ingreso: "0.00",
    egreso: "300.00",
    detalle: null,
    ref_tipo: null,
    ref_id: null,
    creado_en: "2026-07-27T10:00:00-03:00",
    saldo_acumulado: "4700.00",
    ...over,
  };
}

const props = { isLoading: false, isError: false, onRetry: vi.fn() };

describe("MovimientosTable", () => {
  it("muestra la FORMA de cada movimiento", () => {
    // Sin esta columna el listado sin filtrar es ilegible: el saldo acumulado se calcula POR FORMA,
    // así que los números saltan entre particiones distintas y parecen incoherentes. La forma es lo
    // único que explica el salto.
    render(
      <MovimientosTable
        {...props}
        movimientos={[
          mov({ id: 1, forma: "efectivo", saldo_acumulado: "4700.00" }),
          mov({ id: 2, forma: "cheque", saldo_acumulado: "43000.00" }),
        ]}
      />,
    );

    const filas = screen.getAllByRole("row").slice(1); // sin el encabezado
    expect(within(filas[0]!).getByText("Efectivo")).toBeInTheDocument();
    expect(within(filas[1]!).getByText("Cheques en cartera")).toBeInTheDocument();
  });

  it("el encabezado aclara que el saldo es de esa forma", () => {
    render(<MovimientosTable {...props} movimientos={[mov()]} />);

    expect(screen.getByText("de esa forma")).toBeInTheDocument();
  });

  it("distingue el manual del derivado", () => {
    render(
      <MovimientosTable
        {...props}
        movimientos={[
          mov({ id: 1 }),
          mov({ id: 2, ref_tipo: "recibo", ref_id: 12, concepto: "cobranza" }),
        ]}
      />,
    );

    expect(screen.getByText("A mano")).toBeInTheDocument();
    expect(screen.getByText("Recibo #12")).toBeInTheDocument();
  });

  it("muestra 'cargado el' solo cuando la carga no coincide con la fecha del movimiento", () => {
    render(
      <MovimientosTable
        {...props}
        movimientos={[mov({ fecha: "2026-07-20", creado_en: "2026-07-27T10:00:00-03:00" })]}
      />,
    );

    expect(screen.getByText(/cargado el/)).toBeInTheDocument();
  });

  it("sin movimientos explica cómo entran", () => {
    render(<MovimientosTable {...props} movimientos={[]} />);

    expect(screen.getByText("La caja no tiene movimientos")).toBeInTheDocument();
  });
});
