import { ResultTable } from "@/entities/sql-result/ResultTable";
import { cn } from "@/shared/lib/cn";

import type { Message } from "./types";

/** Presenter puro de un mensaje: user vs assistant, cursor de streaming, estados blocked/error. */
export function MessageBubble({ message }: { message: Message }) {
  const isUser = message.role === "user";

  return (
    <div className={cn("flex", isUser ? "justify-end" : "justify-start")}>
      <div
        className={cn(
          "max-w-[85%] rounded-2xl px-4 py-2.5 text-sm",
          isUser ? "bg-primary text-primary-foreground" : "bg-muted text-foreground",
          message.blocked && "bg-destructive/10 text-foreground ring-1 ring-destructive/40",
          message.error && "bg-destructive/10 text-destructive ring-1 ring-destructive/40",
        )}
      >
        <p className="whitespace-pre-wrap break-words">
          {message.content}
          {message.streaming && message.content.length > 0 && (
            <span className="ml-0.5 inline-block h-4 w-[2px] animate-pulse bg-current align-middle" />
          )}
        </p>
        {message.result && <ResultTable result={message.result} />}
      </div>
    </div>
  );
}
