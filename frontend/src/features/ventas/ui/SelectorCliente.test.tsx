import { fireEvent, render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import type { Cliente } from "@/entities/cliente/schema";

import { SelectorCliente } from "./SelectorCliente";

/** El hook pega contra el servidor. Acá lo que se prueba es la pantalla: qué se ofrece, qué se
 *  elige y qué queda a la vista. Lo que la búsqueda devuelve es problema del backend, que tiene
 *  sus propios tests. */
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

function escribir(texto: string) {
  fireEvent.change(screen.getByLabelText("Cliente"), { target: { value: texto } });
}

beforeEach(() => {
  useClientesMock.mockReset();
  responde([]);
});

describe("SelectorCliente", () => {
  it("sin texto no ofrece ninguna lista", () => {
    // Una lista de clientes cualquiera no ayuda a elegir: el padrón tiene 900.
    render(<SelectorCliente value="" onChange={vi.fn()} />);

    expect(screen.queryByRole("listbox")).not.toBeInTheDocument();
  });

  it("busca contra el servidor, no dentro de lo que ya tenía", () => {
    // El bug original: el `<select>` traía una tanda y filtrar ahí adentro decía "no existe" de
    // alguien que sí está cargado.
    render(<SelectorCliente value="" onChange={vi.fn()} />);

    escribir("zurdo");

    expect(useClientesMock).toHaveBeenCalledWith("zurdo", 1);
  });

  it("elegir un cliente devuelve su código", () => {
    const onChange = vi.fn();
    responde([cliente({ codigo: "CLI-000008", denominacion: "Transporte SRL" })]);
    render(<SelectorCliente value="" onChange={onChange} />);

    escribir("transporte");
    fireEvent.mouseDown(screen.getByRole("option", { name: /Transporte SRL/ }));

    expect(onChange).toHaveBeenCalledWith("CLI-000008");
  });

  it("una vez elegido muestra a quién se le está vendiendo", () => {
    responde([cliente({ denominacion: "Transporte SRL" })]);
    render(<SelectorCliente value="" onChange={vi.fn()} />);

    escribir("transporte");
    fireEvent.mouseDown(screen.getByRole("option", { name: /Transporte SRL/ }));

    expect(screen.getByText("Transporte SRL")).toBeInTheDocument();
    expect(screen.queryByRole("combobox")).not.toBeInTheDocument();
  });

  it("se puede elegir sin tocar el mouse", () => {
    // En el mostrador se busca con una mano y se teclea con la otra.
    const onChange = vi.fn();
    responde([
      cliente({ codigo: "CLI-000001", denominacion: "Aceites Uno" }),
      cliente({ id: 2, codigo: "CLI-000002", denominacion: "Aceites Dos" }),
    ]);
    render(<SelectorCliente value="" onChange={onChange} />);

    const input = screen.getByLabelText("Cliente");
    escribir("aceites");
    fireEvent.keyDown(input, { key: "ArrowDown" });
    fireEvent.keyDown(input, { key: "ArrowDown" });
    fireEvent.keyDown(input, { key: "Enter" });

    expect(onChange).toHaveBeenCalledWith("CLI-000002");
  });

  it("Enter sin nada resaltado no elige a nadie", () => {
    // Escribir y apretar Enter para confirmar el texto no puede facturarle al primero de la lista.
    const onChange = vi.fn();
    responde([cliente()]);
    render(<SelectorCliente value="" onChange={onChange} />);

    escribir("gomería");
    fireEvent.keyDown(screen.getByLabelText("Cliente"), { key: "Enter" });

    expect(onChange).not.toHaveBeenCalled();
  });

  it("un cliente dado de baja no se ofrece", () => {
    responde([cliente({ denominacion: "Ex Cliente SA", activo: false })]);
    render(<SelectorCliente value="" onChange={vi.fn()} />);

    escribir("ex");

    expect(screen.queryByRole("option")).not.toBeInTheDocument();
    expect(screen.getByText(/Sin clientes para/)).toBeInTheDocument();
  });

  it("si el padre limpia el cliente, la pantalla deja de mostrarlo", () => {
    // Pasa al emitir la venta: el estado se resetea. Si el nombre quedara, mentiría sobre la
    // venta en curso.
    responde([cliente({ codigo: "CLI-000008", denominacion: "Transporte SRL" })]);
    const { rerender } = render(<SelectorCliente value="" onChange={vi.fn()} />);

    escribir("transporte");
    fireEvent.mouseDown(screen.getByRole("option", { name: /Transporte SRL/ }));
    // El padre es el dueño del código: al elegir, lo baja como prop. Recién cuando lo vuelve a
    // vaciar la pantalla tiene que soltar al cliente.
    rerender(<SelectorCliente value="CLI-000008" onChange={vi.fn()} />);
    expect(screen.getByText("Transporte SRL")).toBeInTheDocument();

    rerender(<SelectorCliente value="" onChange={vi.fn()} />);

    expect(screen.queryByText("Transporte SRL")).not.toBeInTheDocument();
    expect(screen.getByRole("combobox")).toBeInTheDocument();
  });

  it("avisa cuando la búsqueda falla, en vez de decir que no hay clientes", () => {
    // "Sin resultados" ante un error de red hace que el operador dé de alta un cliente que ya
    // existe. El duplicado después hay que arreglarlo a mano.
    responde([], { isError: true });
    render(<SelectorCliente value="" onChange={vi.fn()} />);

    escribir("gomería");

    expect(screen.getByRole("alert")).toHaveTextContent(/No pude buscar/);
  });
});
