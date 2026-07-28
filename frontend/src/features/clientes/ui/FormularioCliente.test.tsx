import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { FormularioCliente } from "./FormularioCliente";

const props = {
  cargando: false,
  error: null,
  ultimoCodigo: null,
  onCrear: vi.fn(),
};

function abrir() {
  fireEvent.click(screen.getByRole("button", { name: /Nuevo cliente/i }));
}

function escribir(label: RegExp, valor: string) {
  fireEvent.change(screen.getByLabelText(label), { target: { value: valor } });
}

describe("FormularioCliente", () => {
  it("arranca cerrado: no ocupa la pantalla hasta que se lo pide", () => {
    render(<FormularioCliente {...props} />);

    expect(screen.queryByLabelText(/Nombre o razón social/i)).not.toBeInTheDocument();
  });

  it("no pide el código: lo genera el servidor", () => {
    render(<FormularioCliente {...props} />);
    abrir();

    expect(screen.queryByLabelText(/[Cc]ódigo/)).not.toBeInTheDocument();
  });

  it("no deja guardar sin denominación", () => {
    render(<FormularioCliente {...props} />);
    abrir();

    expect(screen.getByRole("button", { name: /Dar de alta/i })).toBeDisabled();
  });

  it("con la denominación alcanza: todo lo demás es opcional", () => {
    render(<FormularioCliente {...props} />);
    abrir();
    escribir(/Nombre o razón social/i, "Taller El Rulo");

    expect(screen.getByRole("button", { name: /Dar de alta/i })).toBeEnabled();
  });

  it("manda el payload con los opcionales en null", () => {
    const onCrear = vi.fn();
    render(<FormularioCliente {...props} onCrear={onCrear} />);
    abrir();
    escribir(/Nombre o razón social/i, "Gomería Norte");
    fireEvent.click(screen.getByRole("button", { name: /Dar de alta/i }));

    expect(onCrear).toHaveBeenCalledWith(
      expect.objectContaining({
        denominacion: "Gomería Norte",
        cond_fiscal: "CONSUMIDOR_FINAL",
        cuit: null,
        telefono: null,
      }),
    );
    expect(onCrear.mock.calls[0][0]).not.toHaveProperty("codigo");
  });

  it("un CUIT con el dígito verificador malo avisa y bloquea el botón", () => {
    render(<FormularioCliente {...props} />);
    abrir();
    escribir(/Nombre o razón social/i, "Trucho SA");
    escribir(/CUIT/i, "30-71233445-1");

    expect(screen.getByRole("alert")).toHaveTextContent("dígito verificador");
    expect(screen.getByRole("button", { name: /Dar de alta/i })).toBeDisabled();
  });

  it("un CUIT válido no avisa nada y deja guardar", () => {
    render(<FormularioCliente {...props} />);
    abrir();
    escribir(/Nombre o razón social/i, "Transporte La Veloz");
    escribir(/CUIT/i, "30-71233445-9");

    expect(screen.queryByRole("alert")).not.toBeInTheDocument();
    expect(screen.getByRole("button", { name: /Dar de alta/i })).toBeEnabled();
  });

  it("el CUIT a medias no bloquea si está vacío", () => {
    render(<FormularioCliente {...props} />);
    abrir();
    escribir(/Nombre o razón social/i, "Mostrador");
    escribir(/CUIT/i, "");

    expect(screen.getByRole("button", { name: /Dar de alta/i })).toBeEnabled();
  });

  it("un error del backend se muestra como alerta", () => {
    render(<FormularioCliente {...props} error="Ese código de cliente ya existe." />);
    abrir();

    expect(screen.getByRole("alert")).toHaveTextContent("ya existe");
  });

  it("muestra el código asignado después del alta", () => {
    render(<FormularioCliente {...props} ultimoCodigo="CLI-000001" />);

    // Va en `role="status"`, no en `alert`: es una confirmación, no un problema.
    expect(screen.getByRole("status")).toHaveTextContent("CLI-000001");
  });

  it("mientras guarda, el botón lo dice y no se puede reenviar", () => {
    render(<FormularioCliente {...props} cargando />);
    abrir();
    escribir(/Nombre o razón social/i, "Taller El Rulo");

    expect(screen.getByRole("button", { name: /Guardando/i })).toBeDisabled();
  });

  it("ofrece las cuatro condiciones fiscales del vocabulario", () => {
    render(<FormularioCliente {...props} />);
    abrir();

    const opciones = screen.getByLabelText(/Condición fiscal/i).querySelectorAll("option");
    expect([...opciones].map((o) => o.getAttribute("value"))).toEqual([
      "CONSUMIDOR_FINAL",
      "MONOTRIBUTO",
      "RESPONSABLE_INSCRIPTO",
      "EXENTO",
    ]);
  });

  it("limpia el formulario después de guardar: el siguiente cliente arranca en blanco", () => {
    render(<FormularioCliente {...props} />);
    abrir();
    escribir(/Nombre o razón social/i, "Primero SA");
    fireEvent.click(screen.getByRole("button", { name: /Dar de alta/i }));

    expect(screen.getByLabelText(/Nombre o razón social/i)).toHaveValue("");
  });
});
