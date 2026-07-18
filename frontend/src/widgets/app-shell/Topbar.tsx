import { useRouterState } from "@tanstack/react-router";
import { Menu, Moon, Sun } from "lucide-react";

import { RepuMascot } from "@/features/chat/ui/RepuMascot";
import { useDrawerStore } from "@/features/ui-shell/drawerStore";
import { supabase } from "@/shared/auth/supabase";
import { useThemeStore } from "@/shared/theme/themeStore";
import { Button } from "@/shared/ui/button";

import { NAV_LABELS } from "./nav";

function titulo(pathname: string): string {
  if (pathname === "/") return "Inicio";
  const match = Object.entries(NAV_LABELS)
    .filter(([to]) => to !== "/" && pathname.startsWith(to))
    .sort((a, b) => b[0].length - a[0].length)[0];
  if (match) return match[1];
  if (pathname.startsWith("/catalogo")) return "Catálogo";
  return "Repuestero";
}

export function Topbar() {
  const toggleAssistant = useDrawerStore((s) => s.toggleAssistant);
  const toggleNav = useDrawerStore((s) => s.toggleNav);
  // El logout pasa por Supabase; el AuthGate limpia el token del store al detectar el signOut.
  const cerrarSesion = () => void supabase?.auth.signOut();
  const theme = useThemeStore((s) => s.theme);
  const toggleTheme = useThemeStore((s) => s.toggle);
  const pathname = useRouterState({ select: (s) => s.location.pathname });

  return (
    <header className="flex items-center justify-between border-b border-border bg-background px-4 py-2.5">
      <div className="flex min-w-0 items-center gap-1.5">
        <Button
          variant="ghost"
          size="icon"
          onClick={toggleNav}
          aria-label="Abrir menú de navegación"
          className="h-8 w-8 sm:hidden"
        >
          <Menu className="h-4 w-4" />
        </Button>
        <h1 className="truncate text-sm font-semibold">{titulo(pathname)}</h1>
      </div>
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
        <button
          onClick={toggleAssistant}
          aria-label="Abrir Asistente Repuestero"
          title="Asistente Repuestero"
          className="flex h-9 w-9 items-center justify-center overflow-hidden rounded-full bg-primary/10 ring-1 ring-primary/20 transition-colors hover:bg-primary/20 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 focus-visible:ring-offset-background active:scale-95"
        >
          <RepuMascot className="h-7 w-6 translate-y-0.5" />
        </button>
        <Button variant="ghost" size="sm" onClick={cerrarSesion}>
          Salir
        </Button>
      </div>
    </header>
  );
}
