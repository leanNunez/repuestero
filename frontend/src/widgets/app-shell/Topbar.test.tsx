import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

vi.mock("@tanstack/react-router", () => ({
  useRouterState: () => "/",
}));

const marcarSalidaExplicitaMock = vi.fn();
const signOutMock = vi.fn();

vi.mock("@/shared/auth/demo", () => ({
  marcarSalidaExplicita: () => marcarSalidaExplicitaMock(),
}));

vi.mock("@/shared/auth/supabase", () => ({
  supabase: { auth: { signOut: () => signOutMock() } },
}));

import { Topbar } from "./Topbar";

beforeEach(() => {
  marcarSalidaExplicitaMock.mockReset();
  signOutMock.mockReset().mockResolvedValue(undefined);
  // Llama al orden de invocación en un array compartido para probar que uno pasa ANTES
  // que el otro, no solo que ambos se llamaron.
});

describe("Topbar — cerrar sesión", () => {
  it("marca la salida explícita ANTES de pedirle a Supabase que cierre la sesión", async () => {
    const orden: string[] = [];
    marcarSalidaExplicitaMock.mockImplementation(() => orden.push("marcar"));
    signOutMock.mockImplementation(() => {
      orden.push("signOut");
      return Promise.resolve(undefined);
    });

    const user = userEvent.setup();
    render(<Topbar />);
    await user.click(screen.getByRole("button", { name: "Salir" }));

    // El orden es lo que evita el bug: si signOut() corriera primero, el AuthGate podría
    // ver "sin sesión" y el auto-login de demo volver a entrar ANTES de que se registre la
    // salida explícita — "Salir" quedaría sin efecto visible.
    expect(orden).toEqual(["marcar", "signOut"]);
  });
});
