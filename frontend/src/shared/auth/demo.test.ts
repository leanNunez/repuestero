import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

/** `debeAutoLoguear`/`pideLoginManual` leen `DEMO_MODE` desde config/env, que se resuelve en
 * import-time desde `import.meta.env`. Se mockea el módulo entero para poder prender y apagar
 * DEMO_MODE por test, en vez de depender de variables de entorno reales del proceso de test. */
const envMock = vi.hoisted(() => ({ DEMO_MODE: true, DEMO_EMAIL: "demo@repuestero.app", DEMO_PASSWORD: "123456" }));
vi.mock("@/shared/config/env", () => envMock);

const signInWithPasswordMock = vi.fn();
vi.mock("./supabase", () => ({
  supabase: { auth: { signInWithPassword: (...args: unknown[]) => signInWithPasswordMock(...args) } },
}));

const {
  bannerDemoCerrado,
  cerrarBannerDemo,
  debeAutoLoguear,
  intentarLoginDemo,
  marcarSalidaExplicita,
  pideLoginManual,
} = await import("./demo");

function setUrl(search: string) {
  window.history.replaceState({}, "", `/${search}`);
}

beforeEach(() => {
  envMock.DEMO_MODE = true;
  sessionStorage.clear();
  setUrl("");
  signInWithPasswordMock.mockReset();
});

afterEach(() => {
  sessionStorage.clear();
  setUrl("");
});

describe("debeAutoLoguear", () => {
  it("true cuando DEMO_MODE está prendido y no hay salida explícita ni ?login=1", () => {
    expect(debeAutoLoguear()).toBe(true);
  });

  it("false si DEMO_MODE está apagado (comportamiento de siempre)", () => {
    envMock.DEMO_MODE = false;
    expect(debeAutoLoguear()).toBe(false);
  });

  it("false después de marcarSalidaExplicita() — 'Salir' no debe volver a meter a nadie", () => {
    marcarSalidaExplicita();
    expect(debeAutoLoguear()).toBe(false);
  });

  it("false con ?login=1 en la URL — la vía de escape manual", () => {
    setUrl("?login=1");
    expect(pideLoginManual()).toBe(true);
    expect(debeAutoLoguear()).toBe(false);
  });
});

describe("intentarLoginDemo", () => {
  it("true cuando Supabase no devuelve error", async () => {
    signInWithPasswordMock.mockResolvedValue({ error: null });
    await expect(intentarLoginDemo()).resolves.toBe(true);
    expect(signInWithPasswordMock).toHaveBeenCalledWith({
      email: "demo@repuestero.app",
      password: "123456",
    });
  });

  it("false cuando Supabase devuelve error (credenciales rotadas, proyecto pausado, etc.)", async () => {
    signInWithPasswordMock.mockResolvedValue({ error: new Error("invalid credentials") });
    await expect(intentarLoginDemo()).resolves.toBe(false);
  });
});

describe("banner de demo", () => {
  it("arranca visible (no cerrado) y se marca cerrado por sesión", () => {
    expect(bannerDemoCerrado()).toBe(false);
    cerrarBannerDemo();
    expect(bannerDemoCerrado()).toBe(true);
  });
});
