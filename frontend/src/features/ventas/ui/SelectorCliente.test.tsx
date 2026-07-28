import { fireEvent, render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import type { Cliente } from "@/entities/cliente/schema";

import { SelectorCliente } from "./SelectorCliente";

/** El teclado y las ARIA se prueban en `shared/ui/combobox.test.tsx`. Acá va lo que es de
 *  CLIENTES: qué se le pide al servidor, qué se ofrece y qué se devuelve al elegir. */
const useClientesMock = vi.fn();

vi.mock("@/features/clientes/model/hooks", () => ({
  useClientes: (q: string, page: number) => useClientesMock(q, page),
}));

function cliente(over: Partial<Cliente> = {}): Cliente {
  return {
    id: 1,
    codigo: "CLI-000001",
    denominacion: "Gomería Norte",
    cuit: "30-71233445-9",
    cond_fiscal: "RESPONSABLE_INSCRIPTO",
    limite_cta_cte: 0,
    telefono: null,
    email: null,
    direccion: null,
    activo: true,
    ...over,
  };
}

function responde(items: Cliente[], over = {}) {
  useClientesMock.mockReturnValue({
    data: { items, total: items.length },
    isFetching: false,
    isError: false,
    ...over,
  });
}

const escribir = (texto: string) =>
  fireEvent.change(screen.getByLabelText("Cliente"), { target: { value: texto } });

beforeEach(() => {
  useClientesMock.mockReset();
  responde([]);
});

describe("SelectorCliente", () => {
  it("busca contra el servidor, no dentro de lo que ya tenía", () => {
    // El bug original: el `<select>` traía una tanda y filtrar ahí adentro decía "no existe" de
    // alguien que sí está cargado.
    render(<SelectorCliente value="" onChange={vi.fn()} />);

    escribir("zurdo");

    expect(useClientesMock).toHaveBeenCalledWith("zurdo", 1);
  });

  it("sin texto no ofrece ninguna lista", () => {
    // Una lista de clientes cualquiera no ayuda a elegir: el padrón tiene 900.
    render(<SelectorCliente value="" onChange={vi.fn()} />);

    expect(screen.queryByRole("listbox")).not.toBeInTheDocument();
  });

  it("elegir un cliente devuelve su código", () => {
    const onChange = vi.fn();
    responde([cliente({ codigo: "CLI-000008", denominacion: "Transporte SRL" })]);
    render(<SelectorCliente value="" onChange={onChange} />);

    escribir("transporte");
    fireEvent.mouseDown(screen.getByRole("option", { name: /Transporte SRL/ }));

    expect(onChange).toHaveBeenCalledWith("CLI-000008");
  });

  it("un cliente dado de baja no se ofrece", () => {
    responde([cliente({ denominacion: "Ex Cliente SA", activo: false })]);
    render(<SelectorCliente value="" onChange={vi.fn()} />);

    escribir("ex");

    expect(screen.queryByRole("option")).not.toBeInTheDocument();
    expect(screen.getByText(/Sin resultados/)).toBeInTheDocument();
  });

  it("si el padre limpia el cliente, la pantalla deja de mostrarlo", () => {
    // Pasa al emitir la venta: el estado se resetea. Si el nombre quedara, mentiría sobre la
    // venta en curso.
    responde([cliente({ codigo: "CLI-000008", denominacion: "Transporte SRL" })]);
    const { rerender } = render(<SelectorCliente value="" onChange={vi.fn()} />);

    escribir("transporte");
    fireEvent.mouseDown(screen.getByRole("option", { name: /Transporte SRL/ }));
    rerender(<SelectorCliente value="CLI-000008" onChange={vi.fn()} />);
    expect(screen.getByText("Transporte SRL")).toBeInTheDocument();

    rerender(<SelectorCliente value="" onChange={vi.fn()} />);

    expect(screen.queryByText("Transporte SRL")).not.toBeInTheDocument();
    expect(screen.getByRole("combobox")).toBeInTheDocument();
  });
});
