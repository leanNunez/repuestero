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
      className="group relative mt-5 flex w-full items-center gap-4 rounded-xl border border-primary/25 bg-accent py-4 pl-28 pr-4 text-left shadow-sm transition-shadow hover:shadow-md focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 focus-visible:ring-offset-background"
    >
      {/* Repu sale del marco hacia arriba */}
      <RepuMascot className="pointer-events-none absolute bottom-0 left-4 h-[112px] w-[88px] drop-shadow-md transition-transform duration-300 group-hover:-translate-y-1" />

      <div className="min-w-0 flex-1">
        <div className="flex items-center gap-2">
          <h2 className="text-lg font-bold tracking-tight text-accent-foreground">
            Preguntá sobre tu negocio
          </h2>
          <span className="rounded-full bg-primary px-2 py-0.5 text-[11px] font-semibold text-primary-foreground shadow-sm">
            Repu
          </span>
        </div>

        {/* carrusel de preguntas (rota solo) */}
        <div className="relative mt-1 h-5 overflow-hidden" aria-hidden="true">
          {PREGUNTAS.map((q, idx) => (
            <span
              key={q}
              className="absolute inset-0 flex items-center text-sm text-accent-foreground/75 transition-all duration-500 ease-out"
              style={{
                transform: `translateY(${(idx - activa) * 100}%)`,
                opacity: idx === activa ? 1 : 0,
              }}
            >
              “{q}”
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
