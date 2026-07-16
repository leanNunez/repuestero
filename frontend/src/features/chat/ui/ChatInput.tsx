import { SendHorizontal } from "lucide-react";
import { useState, type FormEvent, type KeyboardEvent } from "react";

import { Button } from "@/shared/ui/button";
import { Textarea } from "@/shared/ui/textarea";

interface Props {
  onSend: (text: string) => void;
  disabled: boolean;
}

export function ChatInput({ onSend, disabled }: Props) {
  const [text, setText] = useState("");

  const submit = () => {
    const t = text.trim();
    if (!t || disabled) return;
    onSend(t);
    setText("");
  };

  const onKeyDown = (e: KeyboardEvent<HTMLTextAreaElement>) => {
    // Enter envía; Shift+Enter hace salto de línea.
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      submit();
    }
  };

  const onSubmit = (e: FormEvent) => {
    e.preventDefault();
    submit();
  };

  return (
    <form
      onSubmit={onSubmit}
      className="flex items-end gap-2 border-t border-border bg-background p-4"
    >
      <Textarea
        value={text}
        onChange={(e) => setText(e.target.value)}
        onKeyDown={onKeyDown}
        placeholder="Escribile a Repu… (stock, precios, clientes)"
        rows={1}
        maxLength={500}
        disabled={disabled}
        aria-label="Mensaje"
      />
      <Button type="submit" size="icon" disabled={disabled || text.trim().length === 0} aria-label="Enviar">
        <SendHorizontal className="h-4 w-4" />
      </Button>
    </form>
  );
}
