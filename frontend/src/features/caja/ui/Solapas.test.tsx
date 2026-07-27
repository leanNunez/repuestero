import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { Solapas } from "./Solapas";

describe("Solapas de caja", () => {
  it("marca la solapa activa", () => {
    render(<Solapas activa="caja" onCambiar={vi.fn()} />);

    expect(screen.getByRole("tab", { name: "Caja" })).toHaveAttribute("aria-selected", "true");
    expect(screen.getByRole("tab", { name: "Cartera" })).toHaveAttribute("aria-selected", "false");
  });

  it("cambia con las flechas", () => {
    const onCambiar = vi.fn();
    render(<Solapas activa="caja" onCambiar={onCambiar} />);

    fireEvent.keyDown(screen.getByRole("tab", { name: "Caja" }), { key: "ArrowRight" });

    expect(onCambiar).toHaveBeenCalledWith("cartera");
  });

  it("solo la solapa activa es parada de Tab", () => {
    // Roving tabindex: un tablist tiene UNA parada de Tab, y adentro se navega con flechas.
    render(<Solapas activa="cartera" onCambiar={vi.fn()} />);

    expect(screen.getByRole("tab", { name: "Cartera" })).toHaveAttribute("tabindex", "0");
    expect(screen.getByRole("tab", { name: "Caja" })).toHaveAttribute("tabindex", "-1");
  });

  it("cada solapa apunta a su panel", () => {
    render(<Solapas activa="caja" onCambiar={vi.fn()} />);

    expect(screen.getByRole("tab", { name: "Caja" })).toHaveAttribute(
      "aria-controls",
      "panel-caja",
    );
  });
});
