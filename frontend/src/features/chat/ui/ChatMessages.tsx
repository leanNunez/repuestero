import { useEffect, useRef } from "react";

import { MessageBubble } from "@/entities/message/MessageBubble";
import type { Message } from "@/entities/message/types";

import { RepuMascot } from "./RepuMascot";

const FASE_LABEL: Record<string, string> = {
  generando: "Generando la consulta…",
  consultando: "Consultando la base…",
  redactando: "Redactando la respuesta…",
};

const SUGERENCIAS = [
  "¿Qué tengo que reponer?",
  "¿Cuáles me dan poco margen?",
  "Stock del filtro de aceite",
  "¿Cuántos clientes tengo?",
];

function EmptyState({ onPick }: { onPick: (q: string) => void }) {
  return (
    <div className="flex h-full flex-col items-center justify-center gap-4 px-2 text-center">
      <RepuMascot state="espera" className="h-28 w-24" />
      <div className="space-y-1">
        <p className="text-base font-semibold">Hola, soy Repu 👋</p>
        <p className="max-w-xs text-sm text-muted-foreground">
          Preguntame lo que quieras de tu negocio y te lo busco al toque.
        </p>
      </div>
      <div className="flex flex-wrap justify-center gap-2">
        {SUGERENCIAS.map((q) => (
          <button
            key={q}
            onClick={() => onPick(q)}
            className="rounded-full border border-teal-500/30 bg-teal-500/10 px-3 py-1.5 text-xs font-medium text-teal-700 transition-colors hover:bg-teal-500/20 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-teal-500/50 dark:text-teal-300"
          >
            {q}
          </button>
        ))}
      </div>
    </div>
  );
}

function ProgressIndicator({ fase }: { fase: string }) {
  return (
    <div className="flex items-center gap-2 text-xs text-muted-foreground" role="status">
      <span className="flex gap-1">
        <span className="h-1.5 w-1.5 animate-bounce rounded-full bg-current [animation-delay:-0.3s]" />
        <span className="h-1.5 w-1.5 animate-bounce rounded-full bg-current [animation-delay:-0.15s]" />
        <span className="h-1.5 w-1.5 animate-bounce rounded-full bg-current" />
      </span>
      {FASE_LABEL[fase] ?? "Pensando…"}
    </div>
  );
}

interface Props {
  messages: Message[];
  fase: string | null;
  status: "idle" | "streaming";
  onPick: (q: string) => void;
}

export function ChatMessages({ messages, fase, status, onPick }: Props) {
  const endRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    endRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, fase]);

  if (messages.length === 0) return <EmptyState onPick={onPick} />;

  const last = messages[messages.length - 1];
  const thinking =
    status === "streaming" && last.role === "assistant" && last.content.length === 0;

  return (
    <div className="flex flex-col gap-4" aria-live="polite">
      {messages.map((m) => (
        <MessageBubble key={m.id} message={m} />
      ))}
      {thinking && <ProgressIndicator fase={fase ?? "generando"} />}
      <div ref={endRef} />
    </div>
  );
}
