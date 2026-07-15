import { X } from "lucide-react";
import { useEffect } from "react";

import { useDrawerStore } from "@/features/ui-shell/drawerStore";
import { cn } from "@/shared/lib/cn";
import { Button } from "@/shared/ui/button";
import { ChatPanel } from "@/widgets/chat-panel/ChatPanel";

/** Copiloto en un panel lateral derecho toggleable. El ChatPanel queda montado (conserva el hilo). */
export function AssistantDrawer() {
  const open = useDrawerStore((s) => s.assistantOpen);
  const close = useDrawerStore((s) => s.closeAssistant);

  useEffect(() => {
    if (!open) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") close();
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [open, close]);

  return (
    <>
      <div
        className={cn(
          "fixed inset-0 z-30 bg-black/30 transition-opacity lg:hidden",
          open ? "opacity-100" : "pointer-events-none opacity-0",
        )}
        onClick={close}
        aria-hidden
      />
      <aside
        className={cn(
          "fixed inset-y-0 right-0 z-40 flex w-full max-w-md flex-col border-l border-border bg-background shadow-xl transition-transform duration-200",
          open ? "translate-x-0" : "translate-x-full",
        )}
        role="dialog"
        aria-label="Asistente"
        inert={!open}
      >
        <header className="flex items-center justify-between border-b border-border px-4 py-3">
          <div>
            <h2 className="text-sm font-semibold">Asistente</h2>
            <p className="text-xs text-muted-foreground">Preguntá sobre tu negocio</p>
          </div>
          <Button variant="ghost" size="icon" onClick={close} aria-label="Cerrar asistente">
            <X className="h-4 w-4" />
          </Button>
        </header>
        <div className="min-h-0 flex-1">
          <ChatPanel />
        </div>
      </aside>
    </>
  );
}
