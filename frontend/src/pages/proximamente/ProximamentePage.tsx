import { useRouterState } from "@tanstack/react-router";
import { Construction } from "lucide-react";

import { useDrawerStore } from "@/features/ui-shell/drawerStore";
import { Badge } from "@/shared/ui/badge";
import { Button } from "@/shared/ui/button";
import { NAV_LABELS } from "@/widgets/app-shell/nav";

/** Pantalla única para los módulos de Fase 2. Se ven en la navegación, pero sin backend todavía. */
export function ProximamentePage() {
  const pathname = useRouterState({ select: (s) => s.location.pathname });
  const toggleAssistant = useDrawerStore((s) => s.toggleAssistant);
  const modulo = NAV_LABELS[pathname] ?? "Este módulo";

  return (
    <div className="flex h-full flex-col items-center justify-center gap-4 p-6 text-center">
      <div className="flex h-12 w-12 items-center justify-center rounded-xl bg-muted">
        <Construction className="h-6 w-6 text-muted-foreground" />
      </div>
      <div className="space-y-2">
        <div className="flex items-center justify-center gap-2">
          <h2 className="text-lg font-semibold">{modulo}</h2>
          <Badge variant="warning">Fase 2</Badge>
        </div>
        <p className="max-w-md text-sm text-muted-foreground">
          Ventas, facturación, caja y cuenta corriente llegan en la Fase 2 — con numeración
          fiscal correcta y libro mayor append-only. Hoy el foco está en el catálogo, los
          tableros y el asistente.
        </p>
      </div>
      <Button variant="outline" size="sm" onClick={toggleAssistant}>
        Mientras tanto, preguntale al asistente
      </Button>
    </div>
  );
}
