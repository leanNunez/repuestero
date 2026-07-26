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

const registrar = () => screen.getByRole("button", { name: "Registrar cobranza" });
const agregar = () => screen.getByRole("button", { name: "+ Agregar forma de pago" });

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
    expect(registrar()).toBeDisabled();
  });

  it("en proveedores habla de pago, no de cobro", () => {
    pintar("proveedores");
    expect(screen.getByLabelText("Fecha del pago")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Registrar pago" })).toBeInTheDocument();
  });

  it("dice qué documento va a emitir", () => {
    // No es lo mismo un recibo que una orden de pago: el operador tiene que saber qué firma.
    pintar();
    expect(screen.getByText(/se emite/)).toHaveTextContent("un recibo");
  });

  it("en proveedores emite una orden de pago", () => {
    pintar("proveedores");
    expect(screen.getByText(/se emite/)).toHaveTextContent("una orden de pago");
  });
});

describe("FormularioImputacion — formas de pago", () => {
  it("arranca con una sola forma, en efectivo", () => {
    pintar();
    expect(screen.getByLabelText("Con qué te pagó")).toHaveValue("efectivo");
  });

  it("con UNA sola forma no pide el importe: es el monto de arriba", () => {
    // Pedirle al operador que escriba el mismo número dos veces es la forma más rápida de que
    // deje de usar la pantalla.
    pintar();
    expect(screen.queryByLabelText("Importe")).not.toBeInTheDocument();
  });

  it("manda el monto canónico, la fecha elegida y el detalle en efectivo", async () => {
    const { onImputar } = pintar();

    // CampoMoneda muestra la máscara es-AR y emite el valor canónico.
    await userEvent.type(screen.getByLabelText("Monto cobrado"), "1234,56");
    fireEvent.change(screen.getByLabelText("Fecha del cobro"), {
      target: { value: "2026-07-20" },
    });
    await userEvent.click(registrar());

    expect(onImputar).toHaveBeenCalledWith("1234.56", "2026-07-20", [
      { forma: "efectivo", monto: "1234.56" },
    ]);
  });

  it("la forma elegida viaja en el detalle", async () => {
    const { onImputar } = pintar();

    await userEvent.type(screen.getByLabelText("Monto cobrado"), "500");
    await userEvent.selectOptions(screen.getByLabelText("Con qué te pagó"), "transferencia");
    await userEvent.click(registrar());

    expect(onImputar).toHaveBeenCalledWith("500", hoyISO(), [
      { forma: "transferencia", monto: "500" },
    ]);
  });

  it("agregar una segunda forma muestra los importes y bloquea hasta repartir", async () => {
    pintar();
    await userEvent.type(screen.getByLabelText("Monto cobrado"), "20000");
    await userEvent.click(agregar());

    const importes = screen.getAllByLabelText("Importe");
    expect(importes).toHaveLength(2);
    // El primero venía llevándose TODO el monto (era la única forma), así que no queda remanente
    // y el segundo entra en cero: el operador reparte a mano y recién ahí cierra.
    expect(importes[0]).toHaveValue("20.000");
    expect(importes[1]).toHaveValue("0");
    expect(registrar()).toBeDisabled();
  });

  it("con dos formas que no suman, el submit queda bloqueado y lo dice", async () => {
    pintar();
    await userEvent.type(screen.getByLabelText("Monto cobrado"), "20000");
    await userEvent.click(agregar());
    // Dejo 20.000 en la primera y 0 en la segunda: suman 20.000... hasta que toco la primera.
    await userEvent.clear(screen.getAllByLabelText("Importe")[0]);
    await userEvent.type(screen.getAllByLabelText("Importe")[0], "5000");

    expect(registrar()).toBeDisabled();
    expect(screen.getByText(/tienen que sumar/)).toBeInTheDocument();
  });

  it("un pago mixto que cierra se puede registrar y viaja completo", async () => {
    const { onImputar } = pintar();
    await userEvent.type(screen.getByLabelText("Monto cobrado"), "20000");
    await userEvent.click(agregar());

    const importes = screen.getAllByLabelText("Importe");
    await userEvent.clear(importes[0]);
    await userEvent.type(importes[0], "5000");
    await userEvent.clear(importes[1]);
    await userEvent.type(importes[1], "15000");
    await userEvent.selectOptions(screen.getByLabelText("Y además"), "cheque");

    expect(registrar()).toBeEnabled();
    await userEvent.click(registrar());

    expect(onImputar).toHaveBeenCalledWith("20000", hoyISO(), [
      { forma: "efectivo", monto: "5000" },
      { forma: "cheque", monto: "15000" },
    ]);
  });

  it("quitar deja una sola forma y vuelve a esconder los importes", async () => {
    pintar();
    await userEvent.type(screen.getByLabelText("Monto cobrado"), "1000");
    await userEvent.click(agregar());
    await userEvent.click(screen.getAllByRole("button", { name: "Quitar" })[1]);

    expect(screen.queryByLabelText("Importe")).not.toBeInTheDocument();
    expect(registrar()).toBeEnabled();
  });

  it("después de registrar, el formulario vuelve a cero", async () => {
    // Si el detalle quedara con dos renglones del cobro anterior, la próxima cobranza saldría
    // mal repartida sin que nadie lo note.
    pintar();
    await userEvent.type(screen.getByLabelText("Monto cobrado"), "1000");
    await userEvent.click(agregar());

    const importes = screen.getAllByLabelText("Importe");
    await userEvent.clear(importes[0]);
    await userEvent.type(importes[0], "400");
    await userEvent.clear(importes[1]);
    await userEvent.type(importes[1], "600");
    await userEvent.click(registrar());

    expect(screen.getByLabelText("Monto cobrado")).toHaveValue("");
    expect(screen.queryByLabelText("Importe")).not.toBeInTheDocument();
    expect(screen.getByLabelText("Con qué te pagó")).toHaveValue("efectivo");
  });

  it("en proveedores el rótulo habla de a quién le pagaste", () => {
    pintar("proveedores");
    expect(screen.getByLabelText("Con qué le pagaste")).toBeInTheDocument();
  });
});
