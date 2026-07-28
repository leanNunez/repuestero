import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { ProveedorTable } from "./ProveedorTable";
import type { Proveedor } from "./schema";

function proveedor(over: Partial<Proveedor> = {}): Proveedor {
  return {
    id: 1,
    codigo: "PRV-000001",
    razon_social: "Distribuidora Central SA",
    cuit: "30-71233445-9",
    telefono: "0341-4567890",
    email: "ventas@central.com",
    activo: true,
    ...over,
  };
}

describe("ProveedorTable", () => {
  it("muestra el proveedor con su código", () => {
    render(<ProveedorTable proveedores={[proveedor()]} />);

    expect(screen.getByText("PRV-000001")).toBeInTheDocument();
    expect(screen.getByText("Distribuidora Central SA")).toBeInTheDocument();
  });

  it("los campos vacíos muestran un guión, no un hueco", () => {
    // Una celda en blanco no distingue "no tiene teléfono" de "se rompió algo".
    render(
      <ProveedorTable
        proveedores={[proveedor({ cuit: null, telefono: null, email: null })]}
      />,
    );

    expect(screen.getAllByText("—")).toHaveLength(3);
  });

  it("NO tiene columna de límite de cuenta corriente", () => {
    // A un proveedor no se le fija un límite de crédito: la deuda va para el otro lado. Si la
    // columna apareciera copiando la tabla de clientes, estaría afirmando algo que no existe.
    render(<ProveedorTable proveedores={[proveedor()]} />);

    expect(screen.queryByText(/límite/i)).not.toBeInTheDocument();
  });

  it("un proveedor de una sola palabra igual tiene avatar", () => {
    render(<ProveedorTable proveedores={[proveedor({ razon_social: "Bulonera" })]} />);

    expect(screen.getByText("B")).toBeInTheDocument();
  });
});
