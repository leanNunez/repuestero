import { act, renderHook } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { useBackendReady } from "./useBackendReady";

const fetchMock = vi.fn();

/** Simula un request que cuelga hasta que ALGO lo aborta — como un backend que acepta la
 * conexión pero nunca responde. Reacciona al AbortSignal como haría un fetch real, así el
 * timeout del hook (setTimeout → controller.abort()) puede desbloquearlo bajo fake timers. */
function fetchQueCuelgaHastaAbortar(
  _url: string,
  opts?: { signal?: AbortSignal },
): Promise<Response> {
  return new Promise((_resolve, reject) => {
    opts?.signal?.addEventListener("abort", () => {
      const err = new Error("Aborted");
      err.name = "AbortError";
      reject(err);
    });
  });
}

beforeEach(() => {
  vi.useFakeTimers();
  vi.stubGlobal("fetch", fetchMock);
  fetchMock.mockReset();
});

afterEach(() => {
  vi.useRealTimers();
  vi.unstubAllGlobals();
});

describe("useBackendReady", () => {
  it("camino caliente: si /health responde ya, no llega a mostrar nada raro y termina en listo", async () => {
    fetchMock.mockResolvedValue({ ok: true });
    const { result } = renderHook(() => useBackendReady());

    expect(result.current.estado.fase).toBe("esperando");
    await act(async () => {
      await vi.advanceTimersByTimeAsync(10);
    });
    expect(result.current.estado.fase).toBe("listo");
  });

  it("no pasa a 'despertando' antes de los 800ms — evita el flash en el camino caliente", async () => {
    fetchMock.mockImplementation(fetchQueCuelgaHastaAbortar);
    const { result } = renderHook(() => useBackendReady());

    await act(async () => {
      await vi.advanceTimersByTimeAsync(500);
    });
    expect(result.current.estado.fase).toBe("esperando");

    await act(async () => {
      await vi.advanceTimersByTimeAsync(400);
    });
    expect(result.current.estado.fase).toBe("despertando");
  });

  it("un intento colgado se aborta por timeout y el loop sigue vivo, no se traba", async () => {
    fetchMock.mockImplementation(fetchQueCuelgaHastaAbortar);
    const { result } = renderHook(() => useBackendReady());

    // intento 0 tiene 4s de timeout; pasado eso debería haberse abortado y seguir
    // reintentando (fase "despertando", nunca "listo" ni trabado en "esperando").
    await act(async () => {
      await vi.advanceTimersByTimeAsync(4_500);
    });
    expect(result.current.estado.fase).toBe("despertando");
  });

  it("reintenta tras fallos y llega a 'listo' apenas /health responde ok", async () => {
    let intentos = 0;
    fetchMock.mockImplementation(() => {
      intentos += 1;
      if (intentos < 3) return Promise.reject(new Error("connection refused"));
      return Promise.resolve({ ok: true });
    });
    const { result } = renderHook(() => useBackendReady());

    await act(async () => {
      await vi.advanceTimersByTimeAsync(20_000);
    });

    expect(result.current.estado.fase).toBe("listo");
    expect(intentos).toBeGreaterThanOrEqual(3);
  });

  it("un 500 (respuesta pero no-ok) también cuenta como fallo y sigue reintentando", async () => {
    fetchMock.mockResolvedValue({ ok: false });
    const { result } = renderHook(() => useBackendReady());

    await act(async () => {
      await vi.advanceTimersByTimeAsync(2_000);
    });
    expect(result.current.estado.fase).toBe("despertando");
  });

  it("nunca queda colgada para siempre: pasado el deadline global, corta en 'agotado'", async () => {
    fetchMock.mockRejectedValue(new Error("connection refused"));
    const { result } = renderHook(() => useBackendReady());

    await act(async () => {
      await vi.advanceTimersByTimeAsync(125_000);
    });

    expect(result.current.estado.fase).toBe("agotado");
  });

  it("reintentar() arranca todo de cero, incluso después de 'agotado'", async () => {
    fetchMock.mockRejectedValue(new Error("connection refused"));
    const { result } = renderHook(() => useBackendReady());

    await act(async () => {
      await vi.advanceTimersByTimeAsync(125_000);
    });
    expect(result.current.estado.fase).toBe("agotado");

    fetchMock.mockReset();
    fetchMock.mockResolvedValue({ ok: true });
    act(() => {
      result.current.reintentar();
    });
    await act(async () => {
      await vi.advanceTimersByTimeAsync(10);
    });

    expect(result.current.estado.fase).toBe("listo");
  });
});
