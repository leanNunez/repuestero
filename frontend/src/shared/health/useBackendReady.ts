import { useEffect, useState } from "react";

import { API_URL } from "@/shared/config/env";

/** Debajo de esto no se muestra nada: evita el flash de la pantalla de arranque en el
 * camino caliente (backend ya despierto), que es el 95% de las visitas. */
const UMBRAL_FLASH_MS = 800;

/** Techo total. Es lo que evita que la pantalla quede colgada para siempre: pasado esto,
 * se corta con un error accionable en vez de reintentar en silencio de por vida. */
const DEADLINE_MS = 120_000;

export type EstadoBackend =
  | { fase: "esperando" }
  | { fase: "despertando"; segundos: number }
  | { fase: "listo" }
  | { fase: "agotado" };

/** Backoff: intento 0 inmediato (timeout 4s); intentos 1-4 con espera +2s/+4s/+6s/+8s
 * (timeout 10s); intentos 5+ cada 5s (timeout 10s). Ver el plan de "siempre arriba" — son
 * los mismos números que usa el cron de keep-alive, para no sorprender a nadie que los lea
 * en los dos lugares. */
function timeoutParaIntento(numero: number): number {
  return numero === 0 ? 4000 : 10000;
}

function esperaAntesDe(numero: number): number {
  return numero <= 4 ? numero * 2000 : 5000;
}

async function backendResponde(signal: AbortSignal): Promise<boolean> {
  try {
    const res = await fetch(`${API_URL}/health`, { signal });
    return res.ok;
  } catch {
    return false; // timeout, red caída, CORS: todo se trata igual — se reintenta
  }
}

/** Pinguea `/health` con backoff hasta que responda o se cumpla el deadline. `/health` no
 * toca la base (a propósito: es el mismo endpoint que usa el cron de keep-alive) — esto
 * mide solo si el PROCESO está arriba, no si Postgres responde. */
export function useBackendReady(): { estado: EstadoBackend; reintentar: () => void } {
  const [estado, setEstado] = useState<EstadoBackend>({ fase: "esperando" });
  const [intento, setIntento] = useState(0);

  useEffect(() => {
    let cancelado = false;
    const inicio = Date.now();
    let flashTimer: ReturnType<typeof setTimeout> | undefined;
    let tickTimer: ReturnType<typeof setInterval> | undefined;

    setEstado({ fase: "esperando" });

    const limpiarTimers = () => {
      if (flashTimer) clearTimeout(flashTimer);
      if (tickTimer) clearInterval(tickTimer);
    };

    flashTimer = setTimeout(() => {
      if (cancelado) return;
      setEstado({ fase: "despertando", segundos: 0 });
      tickTimer = setInterval(() => {
        if (cancelado) return;
        setEstado((e) =>
          e.fase === "despertando" ? { fase: "despertando", segundos: e.segundos + 1 } : e,
        );
      }, 1000);
    }, UMBRAL_FLASH_MS);

    const bucle = async () => {
      let numero = 0;
      while (!cancelado) {
        if (Date.now() - inicio > DEADLINE_MS) {
          limpiarTimers();
          if (!cancelado) setEstado({ fase: "agotado" });
          return;
        }

        const controller = new AbortController();
        const abortTimer = setTimeout(() => controller.abort(), timeoutParaIntento(numero));
        let ok: boolean;
        try {
          ok = await backendResponde(controller.signal);
        } finally {
          clearTimeout(abortTimer);
        }

        if (ok) {
          limpiarTimers();
          if (!cancelado) setEstado({ fase: "listo" });
          return;
        }

        numero += 1;
        await new Promise((r) => setTimeout(r, esperaAntesDe(numero)));
      }
    };

    void bucle();

    return () => {
      cancelado = true;
      limpiarTimers();
    };
  }, [intento]);

  return { estado, reintentar: () => setIntento((n) => n + 1) };
}
