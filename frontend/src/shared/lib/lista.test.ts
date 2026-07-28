import { describe, expect, it } from "vitest";

import { moverIndice } from "./lista";

describe("moverIndice", () => {
  it("desde nada activo, bajar lleva a la primera", () => {
    expect(moverIndice(-1, 1, 5)).toBe(0);
  });

  it("desde nada activo, subir lleva a la última", () => {
    // Es el atajo de siempre: si querés la de abajo de todo, subís una vez.
    expect(moverIndice(-1, -1, 5)).toBe(4);
  });

  it("da la vuelta al pasarse por abajo", () => {
    expect(moverIndice(4, 1, 5)).toBe(0);
  });

  it("da la vuelta al pasarse por arriba", () => {
    expect(moverIndice(0, -1, 5)).toBe(4);
  });

  it("con la lista vacía no hay nada que activar", () => {
    // Sin esto, `opciones[0]` de una lista vacía es `undefined` y Enter elige la nada.
    expect(moverIndice(-1, 1, 0)).toBe(-1);
  });

  it("con una sola opción se queda ahí", () => {
    expect(moverIndice(0, 1, 1)).toBe(0);
  });
});
