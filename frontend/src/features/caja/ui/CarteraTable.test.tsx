import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import type { Cheque } from "@/entities/caja/schema";

import { CarteraTable } from "./CarteraTable";

function cheque(over: Partial<Cheque> = {}): Cheque {
  return {
    id: 1,
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
    ref_id: 7,
    creado_en: "2026-07-27T10:00:00Z",
    ...over,
  };
}

const props = {
  isLoading: false,
  isError: false,
  onRetry: vi.fn(),
  onTransicion: vi.fn(),
  onConciliar: vi.fn(),
  ocupado: null,
};

describe("CarteraTable", () => {
  it("un cheque en cartera ofrece las cuatro salidas", () => {
    render(<CarteraTable {...props} cheques={[cheque()]} />);

    for (const accion of ["Depositar", "Cobrar", "Entregar", "Rechazar"]) {
      expect(screen.getByRole("button", { name: new RegExp(accion, "i") })).toBeInTheDocument();
    }
  });

  it("un cheque depositado NO se puede endosar", () => {
    // El papel ya está en el banco: no se puede entregar lo que no tenés en la mano.
    render(<CarteraTable {...props} cheques={[cheque({ estado: "depositado" })]} />);

    expect(screen.queryByRole("button", { name: /Entregar/i })).not.toBeInTheDocument();
    expect(screen.getByRole("button", { name: /Acreditó/i })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /Rebotó/i })).toBeInTheDocument();
  });

  it("un estado terminal no ofrece ninguna transición", () => {
    for (const estado of ["cobrado", "rechazado", "entregado", "anulado"]) {
      const { unmount } = render(<CarteraTable {...props} cheques={[cheque({ estado })]} />);

      expect(screen.queryByRole("button", { name: /Depositar|Cobrar|Entregar|Rechazar/i })).toBeNull();
      unmount();
    }
  });

  it("un cheque ya conciliado no ofrece conciliar de nuevo", () => {
    render(
      <CarteraTable
        {...props}
        cheques={[cheque({ conciliado: true, fecha_conciliacion: "2026-07-20" })]}
      />,
    );

    expect(screen.queryByRole("button", { name: /Conciliar/i })).not.toBeInTheDocument();
    expect(screen.getByText("Conciliado")).toBeInTheDocument();
  });

  it("sin banco ni número cargados, identifica el papel por su id", () => {
    // Nacen en NULL: un renglón de forma de pago solo trae forma y monto. Decirlo es mejor que
    // mostrar una celda vacía.
    render(<CarteraTable {...props} cheques={[cheque()]} />);

    expect(screen.getByText("Sin datos")).toBeInTheDocument();
    expect(screen.getByText("#1")).toBeInTheDocument();
  });

  it("la fila con una operación en vuelo tiene los botones deshabilitados", () => {
    render(<CarteraTable {...props} cheques={[cheque()]} ocupado={1} />);

    expect(screen.getByRole("button", { name: /Depositar/i })).toBeDisabled();
  });

  it("avisa qué transición se pidió", () => {
    const onTransicion = vi.fn();
    const c = cheque();
    render(<CarteraTable {...props} cheques={[c]} onTransicion={onTransicion} />);

    screen.getByRole("button", { name: /Depositar/i }).click();

    expect(onTransicion).toHaveBeenCalledWith(c, "depositar");
  });

  it("sin cheques explica cómo entran", () => {
    render(<CarteraTable {...props} cheques={[]} />);

    expect(screen.getByText("No hay cheques")).toBeInTheDocument();
  });
});
