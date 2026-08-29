import type { ReactNode } from "react";

import { BootScreen } from "./BootScreen";
import { useBackendReady } from "./useBackendReady";

/** Va AFUERA de `AuthGate` a propósito. Si fuera adentro, el reclutador entraría a la app,
 * vería el `AppShell` completo, y cada panel del dashboard tiraría error de red al mismo
 * tiempo — eso se ve peor que una espera honesta. Acá, el arranque es una sola secuencia
 * coherente: "Despertando el servidor" → (recién ahí) el auto-login de la demo → la app. */
export function BackendGate({ children }: { children: ReactNode }) {
  const { estado, reintentar } = useBackendReady();

  if (estado.fase === "listo") return <>{children}</>;
  if (estado.fase === "esperando") return null; // 0-800ms: nada, para no flashear en el camino caliente
  return <BootScreen estado={estado} onReintentar={reintentar} />;
}
