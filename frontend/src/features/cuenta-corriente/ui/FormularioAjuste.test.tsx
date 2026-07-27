import { fireEvent, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import type { Movimiento } from "@/entities/cuenta-corriente/schema";
import { hoyISO } from "@/shared/lib/format";

import type { ModoAjuste } from "../model/estado";
import { FormularioAjuste } from "./FormularioAjuste";

function mov(over: Partial<Movimiento> = {}): Movimiento {
  return {
    id: 812,
    fecha: "2026-03-20",
    tipo: "cobranza",
    debe: "0.00",
    haber: "5000.00",
    ref_tipo: null,
    ref_id: null,
    motivo: null,
    anulado: false,
    reversible: true,
    anulable: false,
    creado_en: "2026-03-20T14:32:00Z",
    saldo_acumulado: "700.00",
    ...over,
  };
}

function pintar(modo: ModoAjuste | null, over = {}) {
  const props = {
    modo,
    cargando: false,
    error: null,
    onAbrir: vi.fn(),
    onCerrar: vi.fn(),
    onAjustar: vi.fn(),
    ...over,
  };
  render(<FormularioAjuste {...props} />);
  return props;
}

describe("FormularioAjuste", () => {
  it("arranca cerrado: la operación peligrosa no puede ser lo primero que se ve", async () => {
    const { onAbrir } = pintar(null);

    expect(screen.queryByLabelText("Motivo")).toBeNull();
    await userEvent.click(screen.getByRole("button", { name: "Ajustar cuenta" }));

    expect(onAbrir).toHaveBeenCalled();
  });

  describe("modo manual", () => {
    it("no deja registrar sin motivo, aunque haya importe", async () => {
      const { onAjustar } = pintar({ kind: "libre" });

      await userEvent.type(screen.getByLabelText("Importe"), "1200,50");
      expect(screen.getByRole("button", { name: "Registrar ajuste" })).toBeDisabled();

      await userEvent.type(screen.getByLabelText("Motivo"), "no"); // menos del mínimo
      expect(screen.getByRole("button", { name: "Registrar ajuste" })).toBeDisabled();
      expect(onAjustar).not.toHaveBeenCalled();
    });

    it("no deja registrar sin importe, aunque haya motivo", async () => {
      pintar({ kind: "libre" });

      await userEvent.type(screen.getByLabelText("Motivo"), "saldo inicial de la migración");
      expect(screen.getByRole("button", { name: "Registrar ajuste" })).toBeDisabled();
    });

    it("manda el importe canónico en la columna elegida", async () => {
      const { onAjustar } = pintar({ kind: "libre" });

      // CampoMoneda muestra la máscara es-AR pero emite el valor canónico: el backend nunca ve
      // separadores de miles ni coma decimal.
      await userEvent.type(screen.getByLabelText("Importe"), "1200,50");
      await userEvent.type(screen.getByLabelText("Motivo"), "saldo inicial Paradox");
      await userEvent.click(screen.getByRole("button", { name: "Registrar ajuste" }));

      expect(onAjustar).toHaveBeenCalledWith({
        motivo: "saldo inicial Paradox",
        debe: "1200.50",
        fecha: hoyISO(),
      });
    });

    it("puede fechar el ajuste para atrás", async () => {
      // El caso real: un saldo inicial de migración no es de hoy.
      const { onAjustar } = pintar({ kind: "libre" });

      await userEvent.type(screen.getByLabelText("Importe"), "500");
      await userEvent.type(screen.getByLabelText("Motivo"), "saldo inicial Paradox");
      fireEvent.change(screen.getByLabelText("Fecha"), { target: { value: "2026-07-01" } });
      await userEvent.click(screen.getByRole("button", { name: "Registrar ajuste" }));

      expect(onAjustar).toHaveBeenCalledWith(
        expect.objectContaining({ fecha: "2026-07-01" }),
      );
    });

    it("no deja elegir una fecha futura", () => {
      pintar({ kind: "libre" });
      expect(screen.getByLabelText("Fecha")).toHaveAttribute("max", hoyISO());
    });

    it("puede ajustar en el Haber", async () => {
      const { onAjustar } = pintar({ kind: "libre" });

      await userEvent.selectOptions(screen.getByLabelText("Columna"), "haber");
      await userEvent.type(screen.getByLabelText("Importe"), "50");
      await userEvent.type(screen.getByLabelText("Motivo"), "condonación de intereses");
      await userEvent.click(screen.getByRole("button", { name: "Registrar ajuste" }));

      expect(onAjustar).toHaveBeenCalledWith({
        motivo: "condonación de intereses",
        haber: "50",
        fecha: hoyISO(),
      });
    });
  });

  describe("modo reversa", () => {
    const modo: ModoAjuste = { kind: "storno", movimiento: mov() };

    it("NO pide el importe: lo calcula el backend desde el original", () => {
      pintar(modo);

      expect(screen.queryByLabelText("Importe")).toBeNull();
      expect(screen.queryByLabelText("Columna")).toBeNull();
    });

    it("muestra el contra-asiento que va a entrar", () => {
      pintar(modo);

      // Un haber de 5000 se revierte con un debe de 5000. Es un espejo de cortesía para que la
      // persona vea qué va a pasar antes de confirmar.
      expect(screen.getByText(/Se revierte cobranza #812/)).toBeInTheDocument();
      expect(screen.getByText("Debe")).toBeInTheDocument();
      expect(screen.getByText(/5\.000,00/)).toBeInTheDocument();
    });

    it("manda solo el id del movimiento y el motivo", async () => {
      const { onAjustar } = pintar(modo);

      await userEvent.type(screen.getByLabelText("Motivo"), "cargada dos veces");
      await userEvent.click(screen.getByRole("button", { name: "Confirmar reversa" }));

      expect(onAjustar).toHaveBeenCalledWith({
        motivo: "cargada dos veces",
        revierte_movimiento_id: 812,
      });
    });

    it("sigue exigiendo el motivo", async () => {
      pintar(modo);
      expect(screen.getByRole("button", { name: "Confirmar reversa" })).toBeDisabled();
    });

    it("un debe se revierte con un haber", () => {
      pintar({ kind: "storno", movimiento: mov({ debe: "800.00", haber: "0.00", tipo: "ajuste" }) });
      expect(screen.getByText("Haber")).toBeInTheDocument();
    });
  });

  it("muestra el error del backend como alerta", () => {
    pintar({ kind: "libre" }, { error: "Ese movimiento ya fue revertido con un ajuste." });

    expect(screen.getByRole("alert")).toHaveTextContent("ya fue revertido");
  });

  it("cancelar cierra el formulario", async () => {
    const { onCerrar } = pintar({ kind: "libre" });

    await userEvent.click(screen.getByRole("button", { name: "Cancelar" }));
    expect(onCerrar).toHaveBeenCalled();
  });

  it("mientras registra bloquea el submit", () => {
    pintar({ kind: "storno", movimiento: mov() }, { cargando: true });
    expect(screen.getByRole("button", { name: "Registrando…" })).toBeDisabled();
  });
});
