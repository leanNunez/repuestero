import { describe, expect, it } from "vitest";

import { queryPagina } from "./paginacion";

describe("queryPagina", () => {
  it("la página 1 arranca en offset 0", () => {
    // El usuario cuenta desde 1 y el backend desde 0. Errar ese ±1 saltea una página entera.
    expect(queryPagina("", 1, 25)).toBe("limite=25&offset=0");
  });

  it("la página 3 saltea dos páginas completas", () => {
    expect(queryPagina("", 3, 25)).toBe("limite=25&offset=50");
  });

  it("respeta el tamaño de página que le pasan", () => {
    expect(queryPagina("", 2, 10)).toBe("limite=10&offset=10");
  });

  it("sin búsqueda NO manda el parámetro", () => {
    // Un `buscar=` vacío hace que el backend filtre por `%%`. Anda de casualidad, no por diseño.
    expect(queryPagina("   ", 1, 25)).not.toContain("buscar");
  });

  it("manda la búsqueda sin espacios de sobra", () => {
    expect(queryPagina("  gomería  ", 1, 25)).toContain("buscar=gomer%C3%ADa");
  });

  it("escapa lo que rompería la URL", () => {
    // Una denominación con & partiría el query string en dos.
    expect(queryPagina("Ruedas & Cía", 1, 25)).toContain("buscar=Ruedas+%26+C%C3%ADa");
  });

  it("una página inventada no manda un offset negativo", () => {
    // La URL la escribe cualquiera: `?page=0` no puede convertirse en `offset=-25` y un 422.
    expect(queryPagina("", 0, 25)).toContain("offset=0");
  });
});
