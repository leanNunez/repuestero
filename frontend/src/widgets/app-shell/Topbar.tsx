import { useRouterState } from "@tanstack/react-router";
import { Bot, Moon, Sun } from "lucide-react";

import { useDrawerStore } from "@/features/ui-shell/drawerStore";
import { useTokenStore } from "@/shared/auth/tokenStore";
import { useThemeStore } from "@/shared/theme/themeStore";
import { Button } from "@/shared/ui/button";

import { NAV_LABELS } from "./nav";

function titulo(pathname: string): string {
  if (pathname === "/") return "Dashboard";
  const match = Object.entries(NAV_LABELS)
    .filter(([to]) => to !== "/" && pathname.startsWith(to))
    .sort((a, b) => b[0].length - a[0].length)[0];
  if (match) return match[1];
  if (pathname.startsWith("/catalogo")) return "Catálogo";
  return "RepuestOS";
}

export function Topbar() {
  const toggleAssistant = useDrawerStore((s) => s.toggleAssistant);
  const clearToken = useTokenStore((s) => s.clearToken);
  const theme = useThemeStore((s) => s.theme);
  const toggleTheme = useThemeStore((s) => s.toggle);
  const pathname = useRouterState({ select: (s) => s.location.pathname });

  return (
    <header className="flex items-center justify-between border-b border-border bg-background px-4 py-2.5">
      <h1 className="text-sm font-semibold">{titulo(pathname)}</h1>
      <div className="flex items-center gap-1.5">
        <Button
          variant="ghost"
          size="icon"
          onClick={toggleTheme}
          aria-label={theme === "dark" ? "Cambiar a tema claro" : "Cambiar a tema oscuro"}
          className="h-8 w-8"
        >
          {theme === "dark" ? <Sun className="h-4 w-4" /> : <Moon className="h-4 w-4" />}
        </Button>
        <Button variant="default" size="sm" onClick={toggleAssistant}>
          <Bot className="h-4 w-4" />
          Asistente
        </Button>
        <Button variant="ghost" size="sm" onClick={clearToken}>
          Salir
        </Button>
      </div>
    </header>
  );
}
