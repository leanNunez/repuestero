import { Link, useRouterState } from "@tanstack/react-router";
import { Bot, LayoutDashboard, Package } from "lucide-react";
import type { ReactNode } from "react";

import { useDrawerStore } from "@/features/ui-shell/drawerStore";
import { useTokenStore } from "@/shared/auth/tokenStore";
import { Button } from "@/shared/ui/button";
import { AssistantDrawer } from "@/widgets/assistant-drawer/AssistantDrawer";

const NAV = [
  { to: "/", label: "Inicio", icon: LayoutDashboard, exact: true },
  { to: "/catalogo", label: "Catálogo", icon: Package, exact: false },
] as const;

function titulo(pathname: string): string {
  if (pathname === "/") return "Dashboard";
  if (pathname.startsWith("/catalogo")) return "Catálogo";
  return "RepuestOS";
}

export function AppShell({ children }: { children: ReactNode }) {
  const toggleAssistant = useDrawerStore((s) => s.toggleAssistant);
  const clearToken = useTokenStore((s) => s.clearToken);
  const pathname = useRouterState({ select: (s) => s.location.pathname });

  return (
    <div className="flex h-dvh bg-muted/30">
      <aside className="hidden w-56 shrink-0 flex-col border-r border-border bg-background sm:flex">
        <div className="px-4 py-4">
          <span className="text-base font-semibold">RepuestOS</span>
        </div>
        <nav className="flex flex-1 flex-col gap-1 px-2">
          {NAV.map(({ to, label, icon: Icon, exact }) => (
            <Link
              key={to}
              to={to}
              activeOptions={{ exact }}
              className="flex items-center gap-3 rounded-md px-3 py-2 text-sm text-muted-foreground transition-colors hover:bg-muted hover:text-foreground"
              activeProps={{ className: "bg-muted !text-foreground font-medium" }}
            >
              <Icon className="h-4 w-4" />
              {label}
            </Link>
          ))}
        </nav>
      </aside>

      <div className="flex min-w-0 flex-1 flex-col">
        <header className="flex items-center justify-between border-b border-border bg-background px-4 py-3">
          <h1 className="text-sm font-semibold">{titulo(pathname)}</h1>
          <div className="flex items-center gap-2">
            <Button variant="outline" size="sm" onClick={toggleAssistant}>
              <Bot className="h-4 w-4" />
              Asistente
            </Button>
            <Button variant="ghost" size="sm" onClick={clearToken}>
              Salir
            </Button>
          </div>
        </header>
        <main className="min-h-0 flex-1 overflow-y-auto p-6">{children}</main>
      </div>

      <AssistantDrawer />
    </div>
  );
}
