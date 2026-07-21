import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { Pagination } from "./pagination";

describe("Pagination", () => {
  it("no renderiza nada cuando hay una sola página", () => {
    render(<Pagination page={1} pageSize={25} total={10} onPageChange={vi.fn()} />);
    expect(screen.queryByRole("navigation")).toBeNull();
  });

  it("deshabilita Anterior en la primera página y habilita Siguiente", () => {
    render(<Pagination page={1} pageSize={25} total={100} onPageChange={vi.fn()} />);
    expect(screen.getByRole("button", { name: "Anterior" })).toBeDisabled();
    expect(screen.getByRole("button", { name: "Siguiente" })).toBeEnabled();
  });

  it("deshabilita Siguiente en la última página", () => {
    // total=100, pageSize=25 → 4 páginas; page=4 es la última.
    render(<Pagination page={4} pageSize={25} total={100} onPageChange={vi.fn()} />);
    expect(screen.getByRole("button", { name: "Siguiente" })).toBeDisabled();
  });

  it("emite onPageChange con el número clickeado", () => {
    const onPageChange = vi.fn();
    render(<Pagination page={1} pageSize={25} total={100} onPageChange={onPageChange} />);
    fireEvent.click(screen.getByRole("button", { name: "2" }));
    expect(onPageChange).toHaveBeenCalledWith(2);
  });

  it("marca la página actual con aria-current", () => {
    render(<Pagination page={2} pageSize={25} total={100} onPageChange={vi.fn()} />);
    expect(screen.getByRole("button", { name: "2" })).toHaveAttribute("aria-current", "page");
  });

  it("muestra elipsis cuando hay muchas páginas", () => {
    // total=500, pageSize=25 → 20 páginas; en page=10 hay saltos a ambos lados.
    render(<Pagination page={10} pageSize={25} total={500} onPageChange={vi.fn()} />);
    expect(screen.getAllByText("…").length).toBeGreaterThan(0);
    expect(screen.getByRole("button", { name: "1" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "20" })).toBeInTheDocument();
  });
});
