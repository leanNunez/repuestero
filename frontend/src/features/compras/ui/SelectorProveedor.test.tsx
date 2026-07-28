import { fireEvent, render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import type { Proveedor } from "@/entities/proveedor/schema";

import { SelectorProveedor } from "./SelectorProveedor";

const useProveedoresMock = vi.fn();

vi.mock("@/features/proveedores/model/hooks", () => ({
  useProveedores: (q: string, page: number) => useProveedoresMock(q, page),
}));

function proveedor(over: Partial<Proveedor> = {}): Proveedor {
  return {
    id: 1,
    codigo: "PRV-000001",
    razon_social: "Distribuidora Central SA",
    cuit: "30-71233445-9",
    telefono: null,
    email: null,
    activo: true,
    ...over,
  };
}

function responde(items: Proveedor[], over = {}) {
  useProveedoresMock.mockReturnValue({
    data: { items, total: items.length },
    isFetching: false,
    isError: false,
    ...over,
  });
}

const escribir = (texto: string) =>
  fireEvent.change(screen.getByLabelText("Proveedor"), { target: { value: texto } });

beforeEach(() => {
  useProveedoresMock.mockReset();
  responde([]);
});

describe("SelectorProveedor", () => {
  it("busca contra el servidor, no dentro de lo que ya tenía", () => {
    render(<SelectorProveedor value="" onChange={vi.fn()} />);

    escribir("zanella");

    expect(useProveedoresMock).toHaveBeenCalledWith("zanella", 1);
  });

  it("elegir un proveedor devuelve su código", () => {
    const onChange = vi.fn();
    responde([proveedor({ codigo: "PRV-000008", razon_social: "Zanella Repuestos" })]);
    render(<SelectorProveedor value="" onChange={onChange} />);

    escribir("zanella");
    fireEvent.mouseDown(screen.getByRole("option", { name: /Zanella Repuestos/ }));

    expect(onChange).toHaveBeenCalledWith("PRV-000008");
  });

  it("un proveedor dado de baja no se ofrece", () => {
    responde([proveedor({ razon_social: "Ex Proveedor SA", activo: false })]);
    render(<SelectorProveedor value="" onChange={vi.fn()} />);

    escribir("ex");

    expect(screen.queryByRole("option")).not.toBeInTheDocument();
  });

  it("si el padre limpia el proveedor, la pantalla deja de mostrarlo", () => {
    responde([proveedor({ codigo: "PRV-000008", razon_social: "Zanella Repuestos" })]);
    const { rerender } = render(<SelectorProveedor value="" onChange={vi.fn()} />);

    escribir("zanella");
    fireEvent.mouseDown(screen.getByRole("option", { name: /Zanella Repuestos/ }));
    rerender(<SelectorProveedor value="PRV-000008" onChange={vi.fn()} />);
    expect(screen.getByText("Zanella Repuestos")).toBeInTheDocument();

    rerender(<SelectorProveedor value="" onChange={vi.fn()} />);

    expect(screen.queryByText("Zanella Repuestos")).not.toBeInTheDocument();
    expect(screen.getByRole("combobox")).toBeInTheDocument();
  });
});
