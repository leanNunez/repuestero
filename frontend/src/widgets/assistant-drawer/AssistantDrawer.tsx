import { useEffect } from "react";

import { useDrawerStore } from "@/features/ui-shell/drawerStore";
import { cn } from "@/shared/lib/cn";
import { useResizableWidth } from "@/shared/lib/useResizableWidth";
import { ChatPanel } from "@/widgets/chat-panel/ChatPanel";

/** Copiloto en un panel lateral derecho toggleable. El ChatPanel queda montado (conserva el hilo). */
export function AssistantDrawer() {
  const open = useDrawerStore((s) => s.assistantOpen);
  const close = useDrawerStore((s) => s.closeAssistant);
  const { width, onPointerDown, onKeyDown } = useResizableWidth();

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
        style={{ width: `${width}px` }}
        className={cn(
          "fixed inset-y-0 right-0 z-40 flex max-w-[95vw] flex-col border-l border-border bg-background shadow-xl transition-transform duration-200",
          open ? "translate-x-0" : "translate-x-full",
        )}
        role="dialog"
        aria-label="Asistente Repuestero"
        inert={!open}
      >
        {/* Handle para redimensionar arrastrando el borde izquierdo. */}
        <div
          onPointerDown={onPointerDown}
          onKeyDown={onKeyDown}
          role="separator"
          aria-orientation="vertical"
          aria-label="Redimensionar el chat"
          tabIndex={0}
          className="absolute inset-y-0 left-0 z-10 w-1.5 cursor-col-resize bg-transparent transition-colors hover:bg-primary/30 focus-visible:bg-primary/40 focus-visible:outline-none active:bg-primary/50"
        />
        <ChatPanel onClose={close} />
      </aside>
    </>
  );
}
