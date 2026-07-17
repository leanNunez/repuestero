import { X } from "lucide-react";

import { repuStateFromChat } from "@/features/chat/model/repuState";
import { useChat } from "@/features/chat/model/useChat";
import { ChatInput } from "@/features/chat/ui/ChatInput";
import { ChatMessages } from "@/features/chat/ui/ChatMessages";
import { RepuMascot, type RepuState } from "@/features/chat/ui/RepuMascot";
import { Button } from "@/shared/ui/button";

const ESTADO_TEXTO: Record<RepuState, string> = {
  espera: "Listo para ayudarte",
  pensando: "Pensando…",
  error: "Ups, se me complicó",
  respondiendo: "Ahí va…",
};

/** Chat con Repu: cabecera con su estado, historial y input. Conecta el hook con los presenters. */
export function ChatPanel({ onClose }: { onClose: () => void }) {
  const { messages, status, fase, send } = useChat();
  const estado = repuStateFromChat(messages, status);

  return (
    <div className="flex h-full flex-col bg-teal-50/40 dark:bg-teal-950/10">
      <header className="flex items-center gap-3 border-b border-border bg-teal-500/10 px-4 py-2.5">
        <span className="flex h-10 w-10 shrink-0 items-end justify-center overflow-hidden rounded-full bg-teal-500/20 ring-1 ring-teal-500/30">
          <RepuMascot state={estado} className="h-9 w-8 translate-y-0.5" />
        </span>
        <div className="min-w-0 flex-1">
          <p className="text-sm font-semibold">Repu</p>
          <p className="truncate text-xs text-muted-foreground">{ESTADO_TEXTO[estado]}</p>
        </div>
        <Button variant="ghost" size="icon" onClick={onClose} aria-label="Cerrar asistente">
          <X className="h-4 w-4" />
        </Button>
      </header>

      <div className="flex-1 overflow-y-auto p-4">
        <ChatMessages
          messages={messages}
          fase={fase}
          status={status}
          onPick={send}
        />
      </div>

      <ChatInput onSend={send} disabled={status === "streaming"} />
    </div>
  );
}
