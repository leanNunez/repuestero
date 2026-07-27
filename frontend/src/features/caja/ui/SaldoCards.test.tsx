import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import type { SaldoCaja } from "@/entities/caja/schema";

import { SaldoCards } from "./SaldoCards";

const SANO: SaldoCaja = {
  efectivo: "12000.00",
  por_forma: {
    efectivo: "12000.00",
    cheque: "15000.00",
    transferencia: "0",
    tarjeta: "0",
  },
};

describe("SaldoCards", () => {
  it("muestra las cuatro formas", () => {
    render(<SaldoCards saldo={SANO} isLoading={false} />);

    expect(screen.getByText("Efectivo")).toBeInTheDocument();
    expect(screen.getByText("Cheques en cartera")).toBeInTheDocument();
    expect(screen.getByText("Transferencias")).toBeInTheDocument();
    expect(screen.getByText("Tarjeta")).toBeInTheDocument();
  });

  it("un saldo sano no muestra ninguna alerta", () => {
    // Si advirtiera siempre, nadie leería la advertencia cuando importa.
    render(<SaldoCards saldo={SANO} isLoading={false} />);

    expect(screen.queryByRole("alert")).not.toBeInTheDocument();
  });

  it("un saldo negativo muestra la alerta PERSISTENTE", () => {
    // El backend ya avisa al escribir, pero ese acuse se lee una vez y se va. El problema queda,
    // así que la advertencia vive también acá hasta que alguien la resuelva.
    render(
      <SaldoCards
        saldo={{ ...SANO, por_forma: { ...SANO.por_forma, efectivo: "-8500.00" } }}
        isLoading={false}
      />,
    );

    const alerta = screen.getByRole("alert");
    expect(alerta).toHaveTextContent("Efectivo está en negativo");
    expect(alerta).toHaveTextContent("-8500.00");
  });

  it("avisa de CADA forma en negativo, no solo de la primera", () => {
    render(
      <SaldoCards
        saldo={{
          ...SANO,
          por_forma: { ...SANO.por_forma, efectivo: "-100.00", tarjeta: "-50.00" },
        }}
        isLoading={false}
      />,
    );

    const alerta = screen.getByRole("alert");
    expect(alerta).toHaveTextContent("Efectivo");
    expect(alerta).toHaveTextContent("Tarjeta");
  });

  it("el saldo se anuncia: cambia sin que se navegue a ningún lado", () => {
    const { container } = render(<SaldoCards saldo={SANO} isLoading={false} />);

    expect(container.querySelector('[aria-live="polite"]')).toBeInTheDocument();
  });
});
