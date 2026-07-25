import { fireEvent, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import type { Cuenta } from "@/entities/cuenta-corriente/schema";
import { hoyISO } from "@/shared/lib/format";

import type { Solapa } from "../model/estado";
import { FormularioImputacion } from "./FormularioImputacion";

const cuenta: Cuenta = {
  id: 1,
  codigo: "C1754",
  nombre: "Acosta Jorge",
  saldo: "1342845.94",
  limite: null,
};

function pintar(tab: Solapa = "clientes", over = {}) {
  const props = { tab, cuenta, cargando: false, error: null, onImputar: vi.fn(), ...over };
  render(<FormularioImputacion {...props} />);
  return props;
}

describe("FormularioImputacion", () => {
  it("arranca con la fecha de hoy", () => {
    pintar();
    expect(screen.getByLabelText("Fecha del cobro")).toHaveValue(hoyISO());
    expect(screen.getByText(/con fecha/)).toHaveTextContent("de hoy");
  });

  it("no deja elegir una fecha futura", () => {
    // El backend rechaza el futuro con un 422; el input lo hace evidente antes.
    pintar();
    expect(screen.getByLabelText("Fecha del cobro")).toHaveAttribute("max", hoyISO());
  });

  it("manda el monto canónico y la fecha elegida", async () => {
    const { onImputar } = pintar();

    // CampoMoneda muestra la máscara es-AR y emite el valor canónico.
    await userEvent.type(screen.getByLabelText("Monto cobrado"), "1234,56");
    fireEvent.change(screen.getByLabelText("Fecha del cobro"), {
      target: { value: "2026-07-20" },
    });
    await userEvent.click(screen.getByRole("button", { name: "Registrar cobranza" }));

    expect(onImputar).toHaveBeenCalledWith("1234.56", "2026-07-20");
  });

  it("avisa cuando la plata no es de hoy", async () => {
    // El operador tiene que ver que está imputando con otra fecha antes de apretar.
    pintar();
    fireEvent.change(screen.getByLabelText("Fecha del cobro"), {
      target: { value: "2026-07-20" },
    });

    expect(screen.getByText(/con fecha/)).toHaveTextContent("20/07/2026");
  });

  it("no deja registrar sin monto", () => {
    pintar();
    expect(screen.getByRole("button", { name: "Registrar cobranza" })).toBeDisabled();
  });

  it("en proveedores habla de pago, no de cobro", () => {
    pintar("proveedores");
    expect(screen.getByLabelText("Fecha del pago")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Registrar pago" })).toBeInTheDocument();
  });
});
