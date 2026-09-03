import type { Session } from "@supabase/supabase-js";
import { act, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { StrictMode } from "react";
import { beforeEach, describe, expect, it, vi } from "vitest";

const getSessionMock = vi.fn();
const signInWithPasswordMock = vi.fn();
type ChangeCallback = (evento: string, session: Session | null) => void;
const estadoAuth: { callback: ChangeCallback | null } = { callback: null };
const onAuthStateChangeMock = vi.fn((cb: ChangeCallback) => {
  estadoAuth.callback = cb;
  return { data: { subscription: { unsubscribe: vi.fn() } } };
});

vi.mock("./supabase", () => ({
  supabase: {
    auth: {
      getSession: (...args: unknown[]) => getSessionMock(...args),
      onAuthStateChange: (...args: [ChangeCallback]) => onAuthStateChangeMock(...args),
      signInWithPassword: (...args: unknown[]) => signInWithPasswordMock(...args),
    },
  },
  supabaseConfigurado: true,
}));

const debeAutoLoguearMock = vi.fn();
const intentarLoginDemoMock = vi.fn();
vi.mock("./demo", () => ({
  debeAutoLoguear: () => debeAutoLoguearMock() as boolean,
  intentarLoginDemo: () => intentarLoginDemoMock() as Promise<boolean>,
}));

vi.mock("@/shared/config/env", () => ({
  DEMO_EMAIL: "demo@repuestero.app",
  DEMO_PASSWORD: "123456",
}));

import { AuthGate } from "./AuthGate";
import { useTokenStore } from "./tokenStore";

function sesion(token = "jwt-fake"): Session {
  return { access_token: token } as Session;
}

beforeEach(() => {
  getSessionMock.mockReset();
  signInWithPasswordMock.mockReset();
  onAuthStateChangeMock.mockClear();
  debeAutoLoguearMock.mockReset().mockReturnValue(false);
  intentarLoginDemoMock.mockReset();
  estadoAuth.callback = null;
  useTokenStore.getState().clearToken();
});

describe("AuthGate — sin auto-login (comportamiento de siempre)", () => {
  it("sin sesión y sin auto-login configurado, muestra el login vacío", async () => {
    getSessionMock.mockResolvedValue({ data: { session: null } });

    render(
      <AuthGate>
        <p>App</p>
      </AuthGate>,
    );

    await screen.findByText("Entrá para gestionar tu casa de repuestos.");
    expect(screen.getByLabelText("Email")).toHaveValue("");
    expect(intentarLoginDemoMock).not.toHaveBeenCalled();
  });

  it("login manual: submit llama a signInWithPassword y el SIGNED_IN completa el login", async () => {
    getSessionMock.mockResolvedValue({ data: { session: null } });
    signInWithPasswordMock.mockResolvedValue({ error: null });
    const user = userEvent.setup();

    render(
      <AuthGate>
        <p>App</p>
      </AuthGate>,
    );

    await user.type(await screen.findByLabelText("Email"), "yo@repuestero.app");
    await user.type(screen.getByLabelText("Contraseña"), "secreta");
    await user.click(screen.getByRole("button", { name: "Entrar" }));

    expect(signInWithPasswordMock).toHaveBeenCalledWith({
      email: "yo@repuestero.app",
      password: "secreta",
    });

    // Simula el evento que supabase-js emite tras un login exitoso.
    act(() => {
      estadoAuth.callback?.("SIGNED_IN", sesion());
    });

    await screen.findByText("App");
    expect(useTokenStore.getState().token).toBe("jwt-fake");
  });

  it("login manual con error: muestra el mensaje y no rompe", async () => {
    getSessionMock.mockResolvedValue({ data: { session: null } });
    signInWithPasswordMock.mockResolvedValue({ error: new Error("bad creds") });
    const user = userEvent.setup();

    render(
      <AuthGate>
        <p>App</p>
      </AuthGate>,
    );

    await user.type(await screen.findByLabelText("Email"), "yo@repuestero.app");
    await user.type(screen.getByLabelText("Contraseña"), "mal");
    await user.click(screen.getByRole("button", { name: "Entrar" }));

    expect(await screen.findByRole("alert")).toHaveTextContent(/no pudimos entrar/i);
  });
});

describe("AuthGate — con sesión ya activa", () => {
  it("entra directo y NUNCA intenta el auto-login, aunque esté configurado", async () => {
    debeAutoLoguearMock.mockReturnValue(true);
    getSessionMock.mockResolvedValue({ data: { session: sesion() } });

    render(
      <AuthGate>
        <p>App</p>
      </AuthGate>,
    );

    await screen.findByText("App");
    expect(intentarLoginDemoMock).not.toHaveBeenCalled();
  });
});

describe("AuthGate — auto-login de demo", () => {
  it("entra directo, sin login, cuando el auto-login funciona", async () => {
    debeAutoLoguearMock.mockReturnValue(true);
    intentarLoginDemoMock.mockResolvedValue(true);
    getSessionMock
      .mockResolvedValueOnce({ data: { session: null } })
      .mockResolvedValueOnce({ data: { session: sesion() } });

    render(
      <AuthGate>
        <p>App</p>
      </AuthGate>,
    );

    await screen.findByText("App");
    expect(screen.queryByText("Entrá para gestionar tu casa de repuestos.")).not.toBeInTheDocument();
  });

  it("mientras el intento está en vuelo, muestra 'Entrando a la demo…'", async () => {
    debeAutoLoguearMock.mockReturnValue(true);
    getSessionMock
      .mockResolvedValueOnce({ data: { session: null } })
      .mockResolvedValueOnce({ data: { session: sesion() } });
    let resolver: (ok: boolean) => void = () => {};
    intentarLoginDemoMock.mockReturnValue(
      new Promise<boolean>((r) => {
        resolver = r;
      }),
    );

    render(
      <AuthGate>
        <p>App</p>
      </AuthGate>,
    );

    await screen.findByText("Entrando a la demo…");

    await act(async () => {
      resolver(true);
    });

    await screen.findByText("App");
  });

  it("si falla, cae al login PRELLENADO con las credenciales de demo — un clic alcanza", async () => {
    debeAutoLoguearMock.mockReturnValue(true);
    intentarLoginDemoMock.mockResolvedValue(false);
    getSessionMock.mockResolvedValue({ data: { session: null } });

    render(
      <AuthGate>
        <p>App</p>
      </AuthGate>,
    );

    const email = await screen.findByLabelText("Email");
    expect(email).toHaveValue("demo@repuestero.app");
    expect(screen.getByLabelText("Contraseña")).toHaveValue("123456");
    expect(screen.getByText(/no pudimos entrar solos a la demo/i)).toBeInTheDocument();
  });

  it("un solo intento incluso bajo StrictMode (la app real corre así — main.tsx)", async () => {
    debeAutoLoguearMock.mockReturnValue(true);
    intentarLoginDemoMock.mockResolvedValue(false);
    getSessionMock.mockResolvedValue({ data: { session: null } });

    // StrictMode, en dev, monta → desmonta → vuelve a montar el mismo efecto UNA vez para
    // atajar bugs de side-effects. Sin el useRef, esto duplicaría el intento de auto-login
    // (y con él, el riesgo de rate-limit de Supabase Auth).
    render(
      <StrictMode>
        <AuthGate>
          <p>App</p>
        </AuthGate>
      </StrictMode>,
    );
    await screen.findByLabelText("Email");

    expect(intentarLoginDemoMock).toHaveBeenCalledTimes(1);
  });
});
