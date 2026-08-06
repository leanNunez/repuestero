import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { FormularioMovimiento } from "./FormularioMovimiento";

const props = {
  cargando: false,
  error: null,
  advertencias: [] as string[],
  onRegistrar: vi.fn(),
};

function abrir() {
  fireEvent.click(screen.getByRole("button", { name: /Cargar movimiento a mano/i }));
}

describe("FormularioMovimiento", () => {
  it("arranca cerrado para no ocupar la pantalla", () => {
    render(<FormularioMovimiento {...props} />);

    expect(screen.queryByLabelText("Concepto")).not.toBeInTheDocument();
  });

  it("NO ofrece conceptos derivados", () => {
    // Es el invariante del módulo: si hay documento, caja no se toca a mano. Ofrecer "cobranza"
    // acá invitaría a cargar dos veces la misma plata.
    render(<FormularioMovimiento {...props} />);
    abrir();

    const opciones = screen
      .getAllByRole("option")
      .map((o) => (o as HTMLOptionElement).value);

    expect(opciones).not.toContain("cobranza");
    expect(opciones).not.toContain("pago_proveedor");
    expect(opciones).toContain("gasto");
  });

  it("no deja registrar sin monto", () => {
    render(<FormularioMovimiento {...props} />);
    abrir();

    expect(screen.getByRole("button", { name: "Registrar" })).toBeDisabled();
  });

  it("no pide el signo: lo determina el concepto", () => {
    render(<FormularioMovimiento {...props} />);
    abrir();

    expect(screen.queryByLabelText(/ingreso o egreso/i)).not.toBeInTheDocument();
  });

  it("muestra la advertencia de saldo negativo como AVISO, no como error", () => {
    // El movimiento se guardó: advertir no es bloquear. Si esto fuera un `role="alert"` de error,
    // la pantalla estaría diciendo que algo falló cuando no falló nada.
    render(
      <FormularioMovimiento
        {...props}
        advertencias={["El efectivo quedó en -12.500,00. Un saldo negativo no puede pasar."]}
      />,
    );

    expect(screen.getByRole("status")).toHaveTextContent("-12.500,00");
  });

  it("un error de negocio sí se muestra como alerta", () => {
    render(<FormularioMovimiento {...props} error="No existe ese concepto de caja." />);
    abrir();

    expect(screen.getByRole("alert")).toHaveTextContent("No existe ese concepto");
  });
});
