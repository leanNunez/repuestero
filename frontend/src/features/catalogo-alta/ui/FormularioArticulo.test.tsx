import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { FormularioArticulo } from "./FormularioArticulo";

const LISTAS = [
  { id: 1, codigo: "MOST", nombre: "Lista Mostrador" },
  { id: 2, codigo: "MAY", nombre: "Lista Mayorista" },
];

const props = {
  cargando: false,
  error: null,
  errorCodigo: null,
  ultimoCodigo: null,
  advertencias: [],
  rubros: ["FILTROS", "FRENOS"],
  marcas: ["Mann", "Bosch"],
  listas: LISTAS,
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

    expect(screen.queryByLabelText(/^Detalle$/)).not.toBeInTheDocument();
  });

  it("SÍ pide el código: es el del fabricante, no lo inventa el sistema", () => {
    // La diferencia con el alta de clientes, donde el código lo asigna el servidor.
    render(<FormularioArticulo {...props} />);
    abrir();

    expect(screen.getByLabelText(/^Código$/)).toBeInTheDocument();
  });

  it("no deja guardar sin código ni detalle", () => {
    render(<FormularioArticulo {...props} />);
    abrir();

    expect(screen.getByRole("button", { name: /Dar de alta/i })).toBeDisabled();

    escribir(/^Código$/, "MAH-OC90");
    expect(screen.getByRole("button", { name: /Dar de alta/i })).toBeDisabled();

    escribir(/^Detalle$/, "Filtro de aceite");
    expect(screen.getByRole("button", { name: /Dar de alta/i })).toBeEnabled();
  });

  it("manda el payload con el costo en 0 y el IVA por defecto", () => {
    const onCrear = vi.fn().mockResolvedValue(undefined);
    render(<FormularioArticulo {...props} onCrear={onCrear} />);
    abrir();
    escribir(/^Código$/, "MAH-OC90");
    escribir(/^Detalle$/, "Filtro de aceite Gol 1.6");
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

    const input = screen.getByLabelText(/^Código$/);
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
    escribir(/^Código$/, "MAH-OC90");
    escribir(/^Detalle$/, "Filtro de aceite");
    guardar();

    await waitFor(() => expect(onCrear).toHaveBeenCalled());
    expect(screen.getByLabelText(/^Código$/)).toHaveValue("MAH-OC90");
    expect(screen.getByLabelText(/^Detalle$/)).toHaveValue("Filtro de aceite");
  });

  it("cuando el alta SALE, el formulario arranca en blanco para el siguiente", async () => {
    const onCrear = vi.fn().mockResolvedValue(undefined);
    render(<FormularioArticulo {...props} onCrear={onCrear} />);
    abrir();
    escribir(/^Código$/, "MAH-OC90");
    escribir(/^Detalle$/, "Filtro de aceite");
    guardar();

    await waitFor(() => expect(screen.getByLabelText(/^Código$/)).toHaveValue(""));
    expect(screen.getByLabelText(/^Detalle$/)).toHaveValue("");
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
    escribir(/^Código$/, "MAH-OC90");
    escribir(/^Detalle$/, "Filtro de aceite");

    expect(screen.getByRole("button", { name: /Guardando/i })).toBeDisabled();
  });

  it("sugiere los rubros que ya existen PERO deja escribir uno nuevo", () => {
    render(<FormularioArticulo {...props} />);
    abrir();

    // El input está atado a un datalist, no a un select: las opciones se ofrecen, no se imponen.
    const input = screen.getByLabelText(/Rubro/i);
    const lista = document.getElementById(input.getAttribute("list")!);
    expect([...lista!.querySelectorAll("option")].map((o) => o.value)).toEqual([
      "FILTROS",
      "FRENOS",
    ]);

    escribir(/Rubro/i, "SUSPENSION NEUMATICA");
    expect(input).toHaveValue("SUSPENSION NEUMATICA");
    expect(input).toHaveAccessibleDescription(/escribí uno nuevo/i);
  });

  it("un rubro nuevo viaja en el payload tal como se escribió", () => {
    const onCrear = vi.fn().mockResolvedValue(undefined);
    render(<FormularioArticulo {...props} onCrear={onCrear} />);
    abrir();
    escribir(/^Código$/, "MAH-OC90");
    escribir(/^Detalle$/, "Filtro de aceite");
    escribir(/Rubro/i, "Suspensión Neumática");
    escribir(/Marca/i, "Mann-Filter");
    guardar();

    expect(onCrear).toHaveBeenCalledWith(
      expect.objectContaining({ rubro: "Suspensión Neumática", marca: "Mann-Filter" }),
    );
  });

  it("un precio sin lista no deja guardar y dice por qué", () => {
    render(<FormularioArticulo {...props} />);
    abrir();
    escribir(/^Código$/, "MAH-OC90");
    escribir(/^Detalle$/, "Filtro de aceite");
    escribir(/Precio de venta/i, "15000");

    expect(screen.getByRole("button", { name: /Dar de alta/i })).toBeDisabled();
    expect(screen.getByLabelText(/Lista de precios/i)).toHaveAccessibleDescription(
      /Elegí en qué lista/i,
    );
  });

  it("con la lista elegida, el precio y la lista viajan en el payload", () => {
    const onCrear = vi.fn().mockResolvedValue(undefined);
    render(<FormularioArticulo {...props} onCrear={onCrear} />);
    abrir();
    escribir(/^Código$/, "MAH-OC90");
    escribir(/^Detalle$/, "Filtro de aceite");
    escribir(/Precio de venta/i, "15000");
    escribir(/Lista de precios/i, "2");
    guardar();

    expect(onCrear).toHaveBeenCalledWith(
      expect.objectContaining({ precio: "15000", lista_id: 2 }),
    );
  });

  it("sin listas de precio, el bloque queda deshabilitado con el motivo", () => {
    // Caso real: las listas solo las crean el importador y los seeds. Una org sin ninguna tiene
    // que poder cargar artículos igual — el precio se pone después.
    render(<FormularioArticulo {...props} listas={[]} />);
    abrir();
    escribir(/^Código$/, "MAH-OC90");
    escribir(/^Detalle$/, "Filtro de aceite");

    expect(screen.getByLabelText(/Precio de venta/i)).toBeDisabled();
    expect(screen.getByLabelText(/Lista de precios/i)).toBeDisabled();
    expect(screen.getByLabelText(/Precio de venta/i)).toHaveAccessibleDescription(
      /no tiene listas de precio/i,
    );
    expect(screen.getByRole("button", { name: /Dar de alta/i })).toBeEnabled();
  });

  it("muestra las advertencias del alta pegadas a la confirmación", () => {
    render(
      <FormularioArticulo
        {...props}
        ultimoCodigo="MAH-OC90"
        advertencias={["El artículo se creó sin precio de venta."]}
      />,
    );

    expect(screen.getByText(/sin precio de venta/i)).toBeInTheDocument();
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
