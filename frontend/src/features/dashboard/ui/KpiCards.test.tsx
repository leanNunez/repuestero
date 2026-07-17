import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { KpiCards } from "./KpiCards";

describe("KpiCards", () => {
  it("muestra las 4 métricas con sus valores", () => {
    render(
      <KpiCards
        resumen={{
          total_articulos: 20,
          bajo_punto_pedido: 7,
          margen_bajo: 7,
          valor_stock: 4368700,
        }}
      />,
    );
    expect(screen.getByText("Artículos activos")).toBeInTheDocument();
    expect(screen.getByText("20")).toBeInTheDocument();
    expect(screen.getByText("Bajo punto de pedido")).toBeInTheDocument();
    expect(screen.getByText("Valor de stock")).toBeInTheDocument();
  });
});
