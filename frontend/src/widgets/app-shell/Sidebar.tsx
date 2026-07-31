import { Link } from "@tanstack/react-router";

import { useDrawerStore } from "@/features/ui-shell/drawerStore";
import { Badge } from "@/shared/ui/badge";

import { NAV_GROUPS } from "./nav";

export function Sidebar() {
  const closeNav = useDrawerStore((s) => s.closeNav);

  return (
    <nav className="flex flex-1 flex-col gap-5 overflow-y-auto px-3 py-3">
      {NAV_GROUPS.map((group) => (
        <div key={group.label} className="space-y-0.5">
          <p className="px-3 pb-1 text-[11px] font-medium uppercase tracking-wide text-sidebar-foreground/50">
            {group.label}
          </p>
          {group.items.map(({ to, label, icon: Icon, exact, fase }) => (
            <Link
              key={to}
              to={to}
              onClick={closeNav}
              activeOptions={{ exact }}
              // El activo se marca con una barra ámbar a la izquierda, no pintando el fondo:
              // así el acento son unos pocos píxeles y no una superficie entera.
              className="relative flex items-center gap-3 rounded-md py-2 pl-4 pr-3 text-sm text-sidebar-foreground/75 transition-colors hover:bg-white/[0.06] hover:text-sidebar-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-sidebar-accent"
              activeProps={{
                className:
                  "bg-white/[0.08] !text-sidebar-foreground font-medium before:absolute before:left-0 before:top-1.5 before:bottom-1.5 before:w-[3px] before:rounded-full before:bg-sidebar-accent",
              }}
            >
              <Icon className="h-4 w-4 shrink-0" />
              <span className="flex-1 truncate">{label}</span>
              {fase === 2 && (
                <Badge className="shrink-0 bg-white/10 px-1.5 py-0 text-[10px] text-sidebar-foreground/70">
                  Fase 2
                </Badge>
              )}
            </Link>
          ))}
        </div>
      ))}
    </nav>
  );
}
