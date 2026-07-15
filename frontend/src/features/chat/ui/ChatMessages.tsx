import { useEffect, useRef } from "react";

import { MessageBubble } from "@/entities/message/MessageBubble";
import type { Message } from "@/entities/message/types";

const FASE_LABEL: Record<string, string> = {
  generando: "Generando la consulta…",
  consultando: "Consultando la base…",
  redactando: "Redactando la respuesta…",
};

function EmptyState() {
  return (
    <div className="flex h-full flex-col items-center justify-center gap-2 text-center">
      <p className="text-base font-medium">¿En qué te ayudo?</p>
      <p className="max-w-sm text-sm text-muted-foreground">
        Preguntá en lenguaje natural: “¿qué artículos están bajo el punto de pedido?”, “¿cuántos
        clientes tengo?”, “stock del filtro de aceite”.
      </p>
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
}

export function ChatMessages({ messages, fase, status }: Props) {
  const endRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    endRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, fase]);

  if (messages.length === 0) return <EmptyState />;

  const last = messages[messages.length - 1];
  const thinking = status === "streaming" && last.role === "assistant" && last.content.length === 0;

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
