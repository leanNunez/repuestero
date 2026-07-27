import { useRef } from "react";

import { cn } from "@/shared/lib/cn";

import type { Solapa } from "../model/estado";

const SOLAPAS: { id: Solapa; label: string }[] = [
  { id: "caja", label: "Caja" },
  { id: "cartera", label: "Cartera" },
];

interface Props {
  activa: Solapa;
  onCambiar: (tab: Solapa) => void;
}

/** Solapas de verdad: `role="tablist"` con roving tabindex y flechas.
 *
 * Mismo componente que el de cuenta corriente, con otro vocabulario. Un tablist tiene UNA sola
 * parada de Tab —se entra con Tab y se cambia con las flechas—, que es lo que un lector de pantalla
 * anuncia y lo que espera quien navega por teclado. Con dos botones sueltos, Tab pasaría por cada
 * uno y no habría relación entre ellos ni con el panel. */
export function Solapas({ activa, onCambiar }: Props) {
  const refs = useRef<(HTMLButtonElement | null)[]>([]);

  function onKeyDown(e: React.KeyboardEvent, i: number) {
    const paso = e.key === "ArrowRight" ? 1 : e.key === "ArrowLeft" ? -1 : 0;
    if (paso === 0) return;

    e.preventDefault();
    const proxima = (i + paso + SOLAPAS.length) % SOLAPAS.length;
    const solapa = SOLAPAS[proxima];
    if (!solapa) return;

    onCambiar(solapa.id);
    refs.current[proxima]?.focus();
  }

  return (
    <div role="tablist" aria-label="Caja y cartera de cheques" className="flex gap-1">
      {SOLAPAS.map((s, i) => {
        const seleccionada = s.id === activa;
        return (
          <button
            key={s.id}
            ref={(el) => {
              refs.current[i] = el;
            }}
            role="tab"
            id={`solapa-${s.id}`}
            aria-selected={seleccionada}
            aria-controls={`panel-${s.id}`}
            // Roving tabindex: solo la activa es parada de Tab.
            tabIndex={seleccionada ? 0 : -1}
            onClick={() => onCambiar(s.id)}
            onKeyDown={(e) => onKeyDown(e, i)}
            className={cn(
              "rounded-md px-3 py-1.5 text-sm font-medium transition-colors",
              "focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-primary",
              seleccionada
                ? "bg-primary text-primary-foreground"
                : "text-muted-foreground hover:bg-muted hover:text-foreground",
            )}
          >
            {s.label}
          </button>
        );
      })}
    </div>
  );
}
