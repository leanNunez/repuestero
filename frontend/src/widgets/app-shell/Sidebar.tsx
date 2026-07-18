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
          <p className="px-3 pb-1 text-[11px] font-medium uppercase tracking-wide text-white/60">
            {group.label}
          </p>
          {group.items.map(({ to, label, icon: Icon, exact, fase }) => (
            <Link
              key={to}
              to={to}
              onClick={closeNav}
              activeOptions={{ exact }}
              className="flex items-center gap-3 rounded-md px-3 py-2 text-sm text-white/80 transition-colors hover:bg-white/10 hover:text-white focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-white/60 active:scale-[0.98]"
              activeProps={{ className: "bg-white/20 !text-white font-medium" }}
            >
              <Icon className="h-4 w-4 shrink-0" />
              <span className="flex-1 truncate">{label}</span>
              {fase === 2 && (
                <Badge className="shrink-0 bg-white/20 px-1.5 py-0 text-[10px] text-white">
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
