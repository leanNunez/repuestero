import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import type { Movimiento } from "@/entities/cuenta-corriente/schema";

import { FormularioAnulacion } from "./FormularioAnulacion";

function mov(over: Partial<Movimiento> = {}): Movimiento {
  return {
    id: 7,
    fecha: "2026-03-20",
    tipo: "cobranza",
    debe: "0.00",
    haber: "5000.00",
    ref_tipo: "recibo",
    ref_id: 12,
    motivo: null,
    creado_en: "2026-03-20T10:00:00-03:00",
    anulado: false,
    reversible: false,
    anulable: true,
    saldo_acumulado: "1000.00",
    ...over,
  };
}

const props = {
  cargando: false,
  error: null,
  onCerrar: vi.fn(),
  onAnular: vi.fn(),
};

describe("FormularioAnulacion", () => {
  it("sin movimiento no dibuja nada", () => {
    const { container } = render(<FormularioAnulacion {...props} movimiento={null} />);

    expect(container).toBeEmptyDOMElement();
  });

  it("dice QUÉ documento se anula y qué revierte", () => {
    // Anular no es "deshacer una fila": revierte cuenta corriente, caja y cartera a la vez. Si la
    // pantalla no lo dice, la persona no puede saber el alcance de lo que está por apretar.
    render(<FormularioAnulacion {...props} movimiento={mov()} />);

    expect(screen.getByText(/Anular recibo #12/)).toBeInTheDocument();
    expect(screen.getByText(/caja/)).toBeInTheDocument();
    expect(screen.getByText(/cartera/)).toBeInTheDocument();
  });

  it("nombra orden de pago del lado proveedores", () => {
    render(<FormularioAnulacion {...props} movimiento={mov({ ref_tipo: "orden_pago" })} />);

    expect(screen.getByText(/Anular orden de pago/)).toBeInTheDocument();
  });

  it("NO deja anular sin motivo", () => {
    // El backend lo exige, y por una razón: dentro de seis meses la pregunta no va a ser "¿esto se
    // anuló?" —eso se ve— sino POR QUÉ.
    render(<FormularioAnulacion {...props} movimiento={mov()} />);

    expect(screen.getByRole("button", { name: "Anular" })).toBeDisabled();
  });

  it("un motivo en blanco no cuenta como motivo", () => {
    render(<FormularioAnulacion {...props} movimiento={mov()} />);

    const campo = screen.getByLabelText("Motivo");
    campo.focus();

    return userEvent.type(campo, "   ").then(() => {
      expect(screen.getByRole("button", { name: "Anular" })).toBeDisabled();
    });
  });

  it("con motivo, avisa el texto ya recortado", async () => {
    const onAnular = vi.fn();
    render(<FormularioAnulacion {...props} movimiento={mov()} onAnular={onAnular} />);

    await userEvent.type(screen.getByLabelText("Motivo"), "  importe equivocado  ");
    await userEvent.click(screen.getByRole("button", { name: "Anular" }));

    expect(onAnular).toHaveBeenCalledWith("importe equivocado");
  });

  it("muestra el error de negocio del backend", () => {
    render(
      <FormularioAnulacion {...props} movimiento={mov()} error="Ese recibo ya fue anulado." />,
    );

    expect(screen.getByRole("alert")).toHaveTextContent("ya fue anulado");
  });
});
