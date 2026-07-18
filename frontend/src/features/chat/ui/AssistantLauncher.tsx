import { ArrowRight } from "lucide-react";
import { useEffect, useState } from "react";

import { useDrawerStore } from "@/features/ui-shell/drawerStore";

import { RepuMascot } from "./RepuMascot";

const PREGUNTAS = [
  "¿Qué artículos tengo que reponer?",
  "¿Cuáles me están dando poco margen?",
  "¿Qué repuestos le sirven a un Gol Trend?",
  "¿Cuánto vale mi stock hoy?",
  "¿Qué clientes son responsables inscriptos?",
];

/** Hero del asistente. Repu "sale del marco", tagline fija llamativa + carrusel de preguntas. */
export function AssistantLauncher() {
  const toggleAssistant = useDrawerStore((s) => s.toggleAssistant);
  const [activa, setActiva] = useState(0);

  useEffect(() => {
    const id = setInterval(() => setActiva((p) => (p + 1) % PREGUNTAS.length), 3200);
    return () => clearInterval(id);
  }, []);

  return (
    <button
      onClick={toggleAssistant}
      aria-label="Abrir Asistente Repuestero"
      className="group relative mt-5 flex w-full items-center gap-4 rounded-xl border border-primary/25 bg-accent py-4 pl-24 pr-4 text-left shadow-sm transition-shadow hover:shadow-md focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 focus-visible:ring-offset-background sm:pl-28"
    >
      {/* Repu sale del marco hacia arriba (más chico en mobile para no comerse el texto). */}
      <RepuMascot className="pointer-events-none absolute bottom-0 left-4 h-[92px] w-[72px] drop-shadow-md transition-transform duration-300 group-hover:-translate-y-1 sm:h-[112px] sm:w-[88px]" />

      <div className="min-w-0 flex-1">
        <div className="flex min-w-0 items-center gap-2">
          <h2 className="truncate text-base font-bold tracking-tight text-accent-foreground sm:text-lg">
            Preguntá sobre tu negocio
          </h2>
          <span className="shrink-0 rounded-full bg-primary px-2 py-0.5 text-[11px] font-semibold text-primary-foreground shadow-sm">
            Repu
          </span>
        </div>

        {/* carrusel de preguntas (rota solo) */}
        <div className="relative mt-1 h-5 overflow-hidden" aria-hidden="true">
          {PREGUNTAS.map((q, idx) => (
            <span
              key={q}
              className="absolute inset-0 flex items-center transition-all duration-500 ease-out"
              style={{
                transform: `translateY(${(idx - activa) * 100}%)`,
                opacity: idx === activa ? 1 : 0,
              }}
            >
              <span className="w-full truncate text-sm text-accent-foreground/75">“{q}”</span>
            </span>
          ))}
        </div>
      </div>

      <span className="flex h-9 w-9 shrink-0 items-center justify-center rounded-full bg-primary text-primary-foreground transition-transform group-hover:translate-x-0.5">
        <ArrowRight className="h-5 w-5" />
      </span>
    </button>
  );
}
