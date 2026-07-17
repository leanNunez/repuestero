import { Wrench } from "lucide-react";
import type { ReactNode } from "react";

import { AssistantDrawer } from "@/widgets/assistant-drawer/AssistantDrawer";

import { Sidebar } from "./Sidebar";
import { Topbar } from "./Topbar";

/** Pie de la barra: org y usuario del entorno de dev. En Fase 2 sale de Supabase Auth. */
function OrgFooter() {
  return (
    <div className="flex items-center gap-3 border-t border-white/15 px-4 py-3">
      <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-white/15 text-sm font-semibold text-white">
        RD
      </div>
      <div className="min-w-0">
        <p className="truncate text-sm font-medium text-white">Repuestos Demo</p>
        <p className="truncate text-xs text-white/70">admin · dev</p>
      </div>
    </div>
  );
}

export function AppShell({ children }: { children: ReactNode }) {
  return (
    <div className="flex h-dvh bg-muted/30">
      <aside className="hidden w-60 shrink-0 flex-col bg-sidebar text-sidebar-foreground sm:flex">
        <div className="flex items-center gap-2.5 px-4 py-3.5">
          <div className="flex h-7 w-7 items-center justify-center rounded-md bg-white/15 text-white">
            <Wrench className="h-4 w-4" />
          </div>
          <span className="text-base font-semibold tracking-tight">Repuestero</span>
        </div>
        <Sidebar />
        <OrgFooter />
      </aside>

      <div className="flex min-w-0 flex-1 flex-col">
        <Topbar />
        <main className="min-h-0 flex-1 overflow-y-auto">{children}</main>
      </div>

      <AssistantDrawer />
    </div>
  );
}
