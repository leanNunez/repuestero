import { render, screen, within } from "@testing-library/react";
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
  cheques_en_cartera: "15000.00",
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

  describe("la tarjeta de cheques muestra la CARTERA, no el neto del libro", () => {
    // `por_forma.cheque` es el neto de recibidos menos emitidos: un cheque propio resta sin haber
    // sumado nunca, porque no entra a la cartera sino que sale del bolsillo. Rotular ese número
    // "Cheques en cartera" era mentir.

    const CON_EMITIDOS: SaldoCaja = {
      ...SANO,
      // Firmé más cheques de los que tengo: el neto del libro queda en rojo…
      por_forma: { ...SANO.por_forma, cheque: "-4000.00" },
      // …pero la cartera está vacía, que es la verdad de lo que tengo en la mano.
      cheques_en_cartera: "0.00",
    };

    it("muestra el valor de la cartera", () => {
      render(<SaldoCards saldo={CON_EMITIDOS} isLoading={false} />);

      // Dentro de LA tarjeta de cheques, no en cualquier lado: transferencia y tarjeta también
      // están en cero y un `getByText("$ 0,00")` suelto no probaría nada.
      const tarjeta = screen.getByText("Cheques en cartera").closest("div")!;
      expect(within(tarjeta).getByText("$ 0,00")).toBeInTheDocument();
      // El neto del libro (-4.000) NO se muestra en ningún lado.
      expect(screen.queryByText(/-\$\s?4\.000,00/)).not.toBeInTheDocument();
    });

    it("NO grita 'negativo' por el neto del libro", () => {
      // Tener cheques propios en la calle es lo normal. Una alarma que suena siempre es una alarma
      // que nadie mira.
      render(<SaldoCards saldo={CON_EMITIDOS} isLoading={false} />);

      expect(screen.queryByRole("alert")).not.toBeInTheDocument();
    });

    it("pero sí avisa si el EFECTIVO se va a negativo", () => {
      render(
        <SaldoCards
          saldo={{ ...CON_EMITIDOS, por_forma: { ...CON_EMITIDOS.por_forma, efectivo: "-500.00" } }}
          isLoading={false}
        />,
      );

      const alerta = screen.getByRole("alert");
      expect(alerta).toHaveTextContent("Efectivo está en negativo");
      expect(alerta).not.toHaveTextContent("cartera de cheques");
    });
  });
});
