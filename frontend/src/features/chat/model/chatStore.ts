import { create } from "zustand";

import type { Message } from "@/entities/message/types";

import type { StreamEvent } from "./events";
import { reduceStream, type ChatState } from "./streamReducer";

interface ChatStore extends ChatState {
  /** Agrega el mensaje del usuario + un mensaje vacío del asistente (streaming). Devuelve su id. */
  sendUser: (text: string) => string;
  /** Aplica un evento SSE al mensaje del asistente vía el reducer puro. */
  apply: (assistantId: string, ev: StreamEvent) => void;
  reset: () => void;
}

export const useChatStore = create<ChatStore>((set) => ({
  messages: [],
  status: "idle",
  fase: null,

  sendUser: (text) => {
    const user: Message = {
      id: crypto.randomUUID(),
      role: "user",
      content: text,
      streaming: false,
    };
    const assistant: Message = {
      id: crypto.randomUUID(),
      role: "assistant",
      content: "",
      streaming: true,
    };
    set((s) => ({
      messages: [...s.messages, user, assistant],
      status: "streaming",
      fase: null,
    }));
    return assistant.id;
  },

  apply: (assistantId, ev) =>
    set((s) =>
      reduceStream({ messages: s.messages, status: s.status, fase: s.fase }, assistantId, ev),
    ),

  reset: () => set({ messages: [], status: "idle", fase: null }),
}));
