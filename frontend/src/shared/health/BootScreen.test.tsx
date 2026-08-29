import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import { BootScreen } from "./BootScreen";
import type { EstadoBackend } from "./useBackendReady";

describe("BootScreen", () => {
  it("no renderiza nada en 'esperando' — evita el flash en el camino caliente", () => {
    const { container } = render(
      <BootScreen estado={{ fase: "esperando" }} onReintentar={vi.fn()} />,
    );
    expect(container).toBeEmptyDOMElement();
  });

  it("no renderiza nada en 'listo' — ahí ya se está mostrando la app", () => {
    const { container } = render(<BootScreen estado={{ fase: "listo" }} onReintentar={vi.fn()} />);
    expect(container).toBeEmptyDOMElement();
  });

  it("en 'despertando' explica que es costo, no falla, y muestra el contador", () => {
    render(<BootScreen estado={{ fase: "despertando", segundos: 12 }} onReintentar={vi.fn()} />);
    expect(screen.getByText("Despertando el servidor…")).toBeInTheDocument();
    expect(screen.getByText(/infraestructura gratuita/i)).toBeInTheDocument();
    expect(screen.getByText("12s")).toBeInTheDocument();
  });

  it("el hint de 'ya casi' solo aparece pasados los 35s", () => {
    const { rerender } = render(
      <BootScreen estado={{ fase: "despertando", segundos: 20 }} onReintentar={vi.fn()} />,
    );
    expect(screen.queryByText(/ya casi/i)).not.toBeInTheDocument();

    rerender(<BootScreen estado={{ fase: "despertando", segundos: 40 }} onReintentar={vi.fn()} />);
    expect(screen.getByText(/ya casi/i)).toBeInTheDocument();
  });

  it("la barra de progreso nunca llega a 100% sin haber terminado", () => {
    const estado: EstadoBackend = { fase: "despertando", segundos: 300 }; // muy por encima del estimado
    const { container } = render(<BootScreen estado={estado} onReintentar={vi.fn()} />);
    const barra = container.querySelector('[style*="width"]');
    expect(barra).toHaveStyle({ width: "95%" });
  });

  it("en 'agotado' ofrece reintentar y el link al repo, y dispara onReintentar al click", async () => {
    const onReintentar = vi.fn();
    const user = userEvent.setup();
    render(<BootScreen estado={{ fase: "agotado" }} onReintentar={onReintentar} />);

    expect(screen.getByText(/no pudimos despertar el servidor/i)).toBeInTheDocument();
    const link = screen.getByRole("link", { name: /ver el proyecto en github/i });
    expect(link).toHaveAttribute("href", "https://github.com/leanNunez/repuestero");

    await user.click(screen.getByRole("button", { name: "Reintentar" }));
    expect(onReintentar).toHaveBeenCalledOnce();
  });

  it("el contenedor de 'despertando' anuncia actividad para lectores de pantalla", () => {
    render(<BootScreen estado={{ fase: "despertando", segundos: 5 }} onReintentar={vi.fn()} />);
    const status = screen.getByRole("status");
    expect(status).toHaveAttribute("aria-live", "polite");
  });
});
