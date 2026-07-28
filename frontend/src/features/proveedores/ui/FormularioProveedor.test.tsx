import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { FormularioProveedor } from "./FormularioProveedor";

const props = {
  cargando: false,
  error: null,
  ultimoCodigo: null,
  onCrear: vi.fn(),
};

function abrir() {
  fireEvent.click(screen.getByRole("button", { name: /Nuevo proveedor/i }));
}

function escribir(label: string | RegExp, valor: string) {
  fireEvent.change(screen.getByLabelText(label), { target: { value: valor } });
}

describe("FormularioProveedor", () => {
  it("arranca cerrado: la pantalla es el padrón, no el alta", () => {
    render(<FormularioProveedor {...props} />);

    expect(screen.queryByLabelText("Razón social")).not.toBeInTheDocument();
  });

  it("NO pide el código: lo asigna el servidor", () => {
    // Un campo vacío y deshabilitado sería peor que no mostrarlo: invita a preguntarse qué va ahí.
    render(<FormularioProveedor {...props} />);
    abrir();

    expect(screen.queryByLabelText(/código/i)).not.toBeInTheDocument();
  });

  it("con la razón social sola se puede dar de alta", () => {
    const onCrear = vi.fn();
    render(<FormularioProveedor {...props} onCrear={onCrear} />);
    abrir();

    escribir("Razón social", "Distribuidora Sur");
    fireEvent.click(screen.getByRole("button", { name: /Dar de alta/i }));

    expect(onCrear).toHaveBeenCalledWith({
      razon_social: "Distribuidora Sur",
      cuit: null,
      telefono: null,
      email: null,
    });
  });

  it("un CUIT mal escrito avisa y bloquea, sin ir al servidor", () => {
    // Mandarle al backend un CUIT que ya sabemos que está mal es un viaje para volver con un 422.
    const onCrear = vi.fn();
    render(<FormularioProveedor {...props} onCrear={onCrear} />);
    abrir();

    escribir("Razón social", "Trucho SA");
    escribir(/CUIT/, "30-71233445-1");

    expect(screen.getByRole("alert")).toHaveTextContent(/dígito verificador/i);
    expect(screen.getByRole("button", { name: /Dar de alta/i })).toBeDisabled();

    fireEvent.click(screen.getByRole("button", { name: /Dar de alta/i }));
    expect(onCrear).not.toHaveBeenCalled();
  });

  it("un CUIT válido no molesta", () => {
    render(<FormularioProveedor {...props} />);
    abrir();

    escribir("Razón social", "Legal SA");
    escribir(/CUIT/, "30-71233445-9");

    expect(screen.queryByRole("alert")).not.toBeInTheDocument();
    expect(screen.getByRole("button", { name: /Dar de alta/i })).toBeEnabled();
  });

  it("muestra el código que asignó el servidor", () => {
    // Es lo único que la persona no eligió: es lo que necesita ver para saber que el alta salió.
    render(<FormularioProveedor {...props} ultimoCodigo="PRV-000008" />);

    expect(screen.getByRole("status")).toHaveTextContent("PRV-000008");
  });

  it("muestra el error del servidor", () => {
    render(<FormularioProveedor {...props} error="Ese código ya existe. Probá de nuevo." />);
    abrir();

    expect(screen.getByRole("alert")).toHaveTextContent(/ya existe/i);
  });

  it("mientras guarda no se puede volver a apretar", () => {
    render(<FormularioProveedor {...props} cargando />);
    abrir();
    escribir("Razón social", "Distribuidora Sur");

    expect(screen.getByRole("button", { name: /Guardando/i })).toBeDisabled();
  });
});
