import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { Solapas } from "./Solapas";

describe("Solapas", () => {
  it("marca la solapa activa", () => {
    render(<Solapas activa="clientes" onCambiar={vi.fn()} />);

    expect(screen.getByRole("tab", { name: "Clientes" })).toHaveAttribute("aria-selected", "true");
    expect(screen.getByRole("tab", { name: "Proveedores" })).toHaveAttribute(
      "aria-selected",
      "false",
    );
  });

  it("avisa el cambio al clickear", () => {
    const onCambiar = vi.fn();
    render(<Solapas activa="clientes" onCambiar={onCambiar} />);

    fireEvent.click(screen.getByRole("tab", { name: "Proveedores" }));
    expect(onCambiar).toHaveBeenCalledWith("proveedores");
  });

  it("cambia con las flechas", () => {
    const onCambiar = vi.fn();
    render(<Solapas activa="clientes" onCambiar={onCambiar} />);

    fireEvent.keyDown(screen.getByRole("tab", { name: "Clientes" }), { key: "ArrowRight" });
    expect(onCambiar).toHaveBeenCalledWith("proveedores");
  });

  it("las flechas dan la vuelta en los extremos", () => {
    const onCambiar = vi.fn();
    render(<Solapas activa="clientes" onCambiar={onCambiar} />);

    fireEvent.keyDown(screen.getByRole("tab", { name: "Clientes" }), { key: "ArrowLeft" });
    expect(onCambiar).toHaveBeenCalledWith("proveedores");
  });

  it("solo la solapa activa es parada de Tab", () => {
    // Roving tabindex: un tablist tiene UNA parada de Tab, y adentro se navega con flechas.
    render(<Solapas activa="proveedores" onCambiar={vi.fn()} />);

    expect(screen.getByRole("tab", { name: "Proveedores" })).toHaveAttribute("tabindex", "0");
    expect(screen.getByRole("tab", { name: "Clientes" })).toHaveAttribute("tabindex", "-1");
  });

  it("ignora las teclas que no son flechas horizontales", () => {
    const onCambiar = vi.fn();
    render(<Solapas activa="clientes" onCambiar={onCambiar} />);

    fireEvent.keyDown(screen.getByRole("tab", { name: "Clientes" }), { key: "ArrowDown" });
    expect(onCambiar).not.toHaveBeenCalled();
  });
});
