import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import type { EstadoBackend } from "./useBackendReady";

const useBackendReadyMock = vi.fn();

vi.mock("./useBackendReady", () => ({
  useBackendReady: () => useBackendReadyMock() as { estado: EstadoBackend; reintentar: () => void },
}));

import { BackendGate } from "./BackendGate";

function conEstado(estado: EstadoBackend) {
  useBackendReadyMock.mockReturnValue({ estado, reintentar: vi.fn() });
}

describe("BackendGate", () => {
  it("en 'listo' renderiza los children", () => {
    conEstado({ fase: "listo" });
    render(
      <BackendGate>
        <p>Contenido de la app</p>
      </BackendGate>,
    );
    expect(screen.getByText("Contenido de la app")).toBeInTheDocument();
  });

  it("en 'esperando' no renderiza ni los children ni la pantalla de arranque", () => {
    conEstado({ fase: "esperando" });
    const { container } = render(
      <BackendGate>
        <p>Contenido de la app</p>
      </BackendGate>,
    );
    expect(screen.queryByText("Contenido de la app")).not.toBeInTheDocument();
    expect(container).toBeEmptyDOMElement();
  });

  it("en 'despertando' muestra la pantalla de arranque, NO los children", () => {
    conEstado({ fase: "despertando", segundos: 3 });
    render(
      <BackendGate>
        <p>Contenido de la app</p>
      </BackendGate>,
    );
    expect(screen.queryByText("Contenido de la app")).not.toBeInTheDocument();
    expect(screen.getByText("Despertando el servidor…")).toBeInTheDocument();
  });

  it("en 'agotado' muestra el error, NO los children", () => {
    conEstado({ fase: "agotado" });
    render(
      <BackendGate>
        <p>Contenido de la app</p>
      </BackendGate>,
    );
    expect(screen.queryByText("Contenido de la app")).not.toBeInTheDocument();
    expect(screen.getByText(/no pudimos despertar el servidor/i)).toBeInTheDocument();
  });
});
