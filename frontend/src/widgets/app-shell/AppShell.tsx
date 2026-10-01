import { Wrench, XIcon } from "lucide-react";
import { useState, type ReactNode } from "react";

import { useDrawerStore } from "@/features/ui-shell/drawerStore";
import { bannerDemoCerrado, cerrarBannerDemo } from "@/shared/auth/demo";
import { DEMO_MODE } from "@/shared/config/env";
import { cn } from "@/shared/lib/cn";
import { Toaster } from "@/shared/ui/sonner";
import { AssistantDrawer } from "@/widgets/assistant-drawer/AssistantDrawer";

import { Sidebar } from "./Sidebar";
import { Topbar } from "./Topbar";

const REPO_URL = "https://github.com/leanNunez/repuestero";
const PORTFOLIO_URL = "https://leannunez.github.io/myportfolio/";

/** Solo se monta si DEMO_MODE está activo. Hace tres trabajos a la vez: fija expectativas
 * (los datos son de mentira), invita a escribir (que es lo que demuestra el producto), y
 * linkea al repo y al portfolio — que es lo que un reclutador realmente quiere encontrar. */
function BannerDemo() {
  const [visible, setVisible] = useState(() => !bannerDemoCerrado());
  if (!visible) return null;

  return (
    <div className="flex items-center justify-between gap-3 border-b border-border bg-primary/10 px-4 py-2 text-xs text-foreground">
      <p className="min-w-0 truncate">
        Demo pública con datos generados. Podés cargar ventas y compras: se resetean todos los
        días.{" "}
        <a
          href={REPO_URL}
          target="_blank"
          rel="noreferrer"
          className="font-medium underline underline-offset-2"
        >
          Código en GitHub →
        </a>
        {" · "}
        <a
          href={PORTFOLIO_URL}
          target="_blank"
          rel="noopener"
          className="font-medium underline underline-offset-2"
        >
          Hecho por Leandro Nuñez
        </a>
      </p>
      <button
        onClick={() => {
          cerrarBannerDemo();
          setVisible(false);
        }}
        aria-label="Cerrar aviso"
        className="shrink-0 text-muted-foreground hover:text-foreground"
      >
        <XIcon className="h-3.5 w-3.5" />
      </button>
    </div>
  );
}

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
  const navOpen = useDrawerStore((s) => s.navOpen);
  const closeNav = useDrawerStore((s) => s.closeNav);

  return (
    <div className="flex h-dvh bg-muted/30">
      {/* Backdrop del nav en mobile (en sm+ el sidebar es fijo, no hay overlay). */}
      <div
        className={cn(
          "fixed inset-0 z-30 bg-black/30 transition-opacity sm:hidden",
          navOpen ? "opacity-100" : "pointer-events-none opacity-0",
        )}
        onClick={closeNav}
        aria-hidden
      />

      {/* Sidebar: drawer deslizante en mobile, fijo en sm+. */}
      <aside
        className={cn(
          "fixed inset-y-0 left-0 z-40 flex w-60 shrink-0 flex-col bg-sidebar text-sidebar-foreground transition-transform duration-200 sm:static sm:translate-x-0",
          navOpen ? "translate-x-0" : "-translate-x-full",
        )}
      >
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
        {DEMO_MODE && <BannerDemo />}
        <Topbar />
        <main className="min-h-0 flex-1 overflow-y-auto">{children}</main>
      </div>

      <AssistantDrawer />

      {/* Solo confirmaciones efímeras (docs/art-direction.md). Los errores van inline:
          un toast se va y el problema queda. */}
      <Toaster position="bottom-right" />
    </div>
  );
}
