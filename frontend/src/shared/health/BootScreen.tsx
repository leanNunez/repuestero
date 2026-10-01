import type { ReactNode } from "react";

import { Button } from "@/shared/ui/button";

import type { EstadoBackend } from "./useBackendReady";

const REPO_URL = "https://github.com/leanNunez/repuestero";
const PORTFOLIO_URL = "https://leannunez.github.io/myportfolio/";
/** Estimado para la barra de progreso, no una promesa: un cold start típico ronda esto. */
const ESTIMADO_SEGUNDOS = 60;

/** Presentacional, sin lógica propia — así es testeable sola y reusable (el `AuthGate` la
 * comparte para su paso "Entrando a la demo…"). No renderiza nada en "esperando" (el flash
 * del camino caliente) ni en "listo" (ahí ya se está mostrando la app). */
export function BootScreen({
  estado,
  onReintentar,
}: {
  estado: EstadoBackend;
  onReintentar: () => void;
}) {
  if (estado.fase === "esperando" || estado.fase === "listo") return null;

  if (estado.fase === "agotado") {
    return (
      <Pantalla>
        <p className="text-sm font-medium">No pudimos despertar el servidor.</p>
        <p className="max-w-sm text-sm text-muted-foreground">
          Puede que esté momentáneamente caído. Reintentá, o mirá el estado del proyecto en
          GitHub mientras tanto.
        </p>
        <div className="flex flex-col items-center gap-2">
          <Button onClick={onReintentar}>Reintentar</Button>
          <a
            href={REPO_URL}
            target="_blank"
            rel="noreferrer"
            className="text-xs text-muted-foreground underline underline-offset-2 hover:text-foreground"
          >
            Ver el proyecto en GitHub
          </a>
          <a
            href={PORTFOLIO_URL}
            target="_blank"
            rel="noopener"
            className="text-xs text-muted-foreground underline underline-offset-2 hover:text-foreground"
          >
            Hecho por Leandro Nuñez
          </a>
        </div>
      </Pantalla>
    );
  }

  const { segundos } = estado;
  // Topeado en 95%: nunca mostrar 100% sin haber llegado — eso es mentirle a quien espera.
  const progreso = Math.min(95, Math.round((segundos / ESTIMADO_SEGUNDOS) * 100));

  return (
    <Pantalla>
      <div role="status" aria-live="polite" className="space-y-3">
        <p className="text-sm font-medium">Despertando el servidor…</p>
        <p className="max-w-sm text-sm text-muted-foreground">
          Esta demo corre en infraestructura gratuita. El backend se apaga cuando nadie lo usa
          y tarda hasta un minuto en volver. Es una decisión de costo, no una falla.
        </p>
        {segundos > 35 && (
          <p className="max-w-sm text-xs text-muted-foreground">
            Ya casi. Los cold starts largos rondan el minuto.
          </p>
        )}
        <div className="mx-auto h-1.5 w-56 overflow-hidden rounded-full bg-muted">
          <div
            className="h-full bg-primary transition-[width] duration-500 motion-reduce:transition-none"
            style={{ width: `${progreso}%` }}
          />
        </div>
        {/* aria-hidden: el contador visual actualiza cada segundo — anunciarlo en cada tick
            atropellaría al lector de pantalla. El role="status" de arriba ya avisa que hay
            actividad; el texto fijo alcanza para quien usa lector de pantalla. */}
        <p aria-hidden className="text-xs text-muted-foreground">
          {segundos}s
        </p>
      </div>
    </Pantalla>
  );
}

function Pantalla({ children }: { children: ReactNode }) {
  return (
    <div className="mx-auto flex min-h-dvh max-w-sm flex-col items-center justify-center gap-4 p-6 text-center">
      {children}
    </div>
  );
}
