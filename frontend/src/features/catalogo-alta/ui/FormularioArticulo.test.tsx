import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { FormularioArticulo } from "./FormularioArticulo";

const props = {
  cargando: false,
  error: null,
  errorCodigo: null,
  ultimoCodigo: null,
  onCrear: vi.fn().mockResolvedValue(undefined),
};

function abrir() {
  fireEvent.click(screen.getByRole("button", { name: /Nuevo artículo/i }));
}

function escribir(label: RegExp, valor: string) {
  fireEvent.change(screen.getByLabelText(label), { target: { value: valor } });
}

function guardar() {
  fireEvent.click(screen.getByRole("button", { name: /Dar de alta/i }));
}

describe("FormularioArticulo", () => {
  it("arranca cerrado: no ocupa la pantalla hasta que se lo pide", () => {
    render(<FormularioArticulo {...props} />);

    expect(screen.queryByLabelText(/Detalle/i)).not.toBeInTheDocument();
  });

  it("SÍ pide el código: es el del fabricante, no lo inventa el sistema", () => {
    // La diferencia con el alta de clientes, donde el código lo asigna el servidor.
    render(<FormularioArticulo {...props} />);
    abrir();

    expect(screen.getByLabelText(/Código/i)).toBeInTheDocument();
  });

  it("no deja guardar sin código ni detalle", () => {
    render(<FormularioArticulo {...props} />);
    abrir();

    expect(screen.getByRole("button", { name: /Dar de alta/i })).toBeDisabled();

    escribir(/Código/i, "MAH-OC90");
    expect(screen.getByRole("button", { name: /Dar de alta/i })).toBeDisabled();

    escribir(/Detalle/i, "Filtro de aceite");
    expect(screen.getByRole("button", { name: /Dar de alta/i })).toBeEnabled();
  });

  it("manda el payload con el costo en 0 y el IVA por defecto", () => {
    const onCrear = vi.fn().mockResolvedValue(undefined);
    render(<FormularioArticulo {...props} onCrear={onCrear} />);
    abrir();
    escribir(/Código/i, "MAH-OC90");
    escribir(/Detalle/i, "Filtro de aceite Gol 1.6");
    guardar();

    expect(onCrear).toHaveBeenCalledWith(
      expect.objectContaining({
        codigo: "MAH-OC90",
        detalle: "Filtro de aceite Gol 1.6",
        costo: "0",
        alicuota_iva: "21.00",
        marca: null,
        rubro: null,
        precio: null,
        lista_id: null,
      }),
    );
  });

  it("el código repetido se muestra DEBAJO del campo código", () => {
    // Y no al pie del formulario: es el problema de un campo, y el campo está a diez centímetros.
    render(
      <FormularioArticulo {...props} errorCodigo="Ya existe un artículo con ese código." />,
    );
    abrir();

    const input = screen.getByLabelText(/Código/i);
    expect(input).toHaveAttribute("aria-invalid", "true");
    expect(input).toHaveAccessibleDescription(/Ya existe un artículo con ese código/i);
  });

  it("cuando el alta FALLA, lo tipeado queda en pantalla", async () => {
    // La divergencia deliberada con el alta de clientes. Acá el código lo tipea la persona y el
    // 409 es esperable: limpiar en el submit le borraría todo justo cuando tiene que corregir un
    // campo. Se limpia en el éxito, no antes.
    const onCrear = vi.fn().mockRejectedValue(new Error("409"));
    render(<FormularioArticulo {...props} onCrear={onCrear} />);
    abrir();
    escribir(/Código/i, "MAH-OC90");
    escribir(/Detalle/i, "Filtro de aceite");
    guardar();

    await waitFor(() => expect(onCrear).toHaveBeenCalled());
    expect(screen.getByLabelText(/Código/i)).toHaveValue("MAH-OC90");
    expect(screen.getByLabelText(/Detalle/i)).toHaveValue("Filtro de aceite");
  });

  it("cuando el alta SALE, el formulario arranca en blanco para el siguiente", async () => {
    const onCrear = vi.fn().mockResolvedValue(undefined);
    render(<FormularioArticulo {...props} onCrear={onCrear} />);
    abrir();
    escribir(/Código/i, "MAH-OC90");
    escribir(/Detalle/i, "Filtro de aceite");
    guardar();

    await waitFor(() => expect(screen.getByLabelText(/Código/i)).toHaveValue(""));
    expect(screen.getByLabelText(/Detalle/i)).toHaveValue("");
  });

  it("un error general se muestra como alerta al pie", () => {
    render(<FormularioArticulo {...props} error="No se pudo guardar el artículo." />);
    abrir();

    expect(screen.getByRole("alert")).toHaveTextContent("No se pudo guardar");
  });

  it("muestra el código del artículo dado de alta", () => {
    render(<FormularioArticulo {...props} ultimoCodigo="MAH-OC90" />);

    // Va en `role="status"`, no en `alert`: es una confirmación, no un problema.
    expect(screen.getByRole("status")).toHaveTextContent("MAH-OC90");
  });

  it("mientras guarda, el botón lo dice y no se puede reenviar", () => {
    render(<FormularioArticulo {...props} cargando />);
    abrir();
    escribir(/Código/i, "MAH-OC90");
    escribir(/Detalle/i, "Filtro de aceite");

    expect(screen.getByRole("button", { name: /Guardando/i })).toBeDisabled();
  });

  it("ofrece las cuatro alícuotas del vocabulario de AFIP", () => {
    render(<FormularioArticulo {...props} />);
    abrir();

    const opciones = screen.getByLabelText(/IVA/i).querySelectorAll("option");
    expect([...opciones].map((o) => o.getAttribute("value"))).toEqual([
      "21.00",
      "10.50",
      "27.00",
      "0.00",
    ]);
  });
});
