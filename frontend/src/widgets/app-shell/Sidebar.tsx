import { Link } from "@tanstack/react-router";

import { Badge } from "@/shared/ui/badge";

import { NAV_GROUPS } from "./nav";

export function Sidebar() {
  return (
    <nav className="flex flex-1 flex-col gap-5 overflow-y-auto px-3 py-3">
      {NAV_GROUPS.map((group) => (
        <div key={group.label} className="space-y-0.5">
          <p className="px-3 pb-1 text-[11px] font-medium uppercase tracking-wide text-muted-foreground">
            {group.label}
          </p>
          {group.items.map(({ to, label, icon: Icon, exact, fase }) => (
            <Link
              key={to}
              to={to}
              activeOptions={{ exact }}
              className="flex items-center gap-3 rounded-md px-3 py-2 text-sm text-muted-foreground transition-colors hover:bg-muted hover:text-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 focus-visible:ring-offset-background active:scale-[0.98]"
              activeProps={{ className: "bg-muted !text-foreground font-medium" }}
            >
              <Icon className="h-4 w-4 shrink-0" />
              <span className="flex-1 truncate">{label}</span>
              {fase === 2 && (
                <Badge className="shrink-0 px-1.5 py-0 text-[10px]">Fase 2</Badge>
              )}
            </Link>
          ))}
        </div>
      ))}
    </nav>
  );
}
