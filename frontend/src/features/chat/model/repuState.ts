import type { Message } from "@/entities/message/types";
import type { RepuState } from "@/features/chat/ui/RepuMascot";

/** Deriva el gesto de Repu del estado del chat. Pura → testeable en frío. */
export function repuStateFromChat(
  messages: Message[],
  status: "idle" | "streaming",
): RepuState {
  const last = messages[messages.length - 1];

  if (last?.role === "assistant" && (last.error || last.blocked)) return "error";

  if (status === "streaming") {
    // Antes del primer token: pensando. Con tokens llegando: respondiendo.
    return last?.role === "assistant" && last.content.length === 0
      ? "pensando"
      : "respondiendo";
  }

  // Idle: si lo último fue una respuesta del asistente, queda contento; si no, en espera.
  if (last?.role === "assistant" && last.content.length > 0) return "respondiendo";
  return "espera";
}
