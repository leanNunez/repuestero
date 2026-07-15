import { useChat } from "@/features/chat/model/useChat";
import { ChatInput } from "@/features/chat/ui/ChatInput";
import { ChatMessages } from "@/features/chat/ui/ChatMessages";

/** Compone el chat: historial con scroll + input. Container que conecta el hook con los presenters. */
export function ChatPanel() {
  const { messages, status, fase, send } = useChat();

  return (
    <div className="flex h-full flex-col">
      <div className="flex-1 overflow-y-auto p-4">
        <ChatMessages messages={messages} fase={fase} status={status} />
      </div>
      <ChatInput onSend={send} disabled={status === "streaming"} />
    </div>
  );
}
