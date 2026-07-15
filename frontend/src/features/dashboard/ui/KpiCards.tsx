import { Boxes, PackageX, TrendingDown, Wallet } from "lucide-react";
import type { ReactNode } from "react";

import { formatMoney, formatNumber } from "@/shared/lib/format";
import { Card } from "@/shared/ui/card";

import type { Resumen } from "../schema";

function Kpi({
  label,
  value,
  icon,
  tone,
}: {
  label: string;
  value: ReactNode;
  icon: ReactNode;
  tone: string;
}) {
  return (
    <Card className="p-4">
      <div className="flex items-center justify-between">
        <span className="text-xs text-muted-foreground">{label}</span>
        <span className={tone}>{icon}</span>
      </div>
      <p className="mt-2 text-2xl font-semibold tabular-nums">{value}</p>
    </Card>
  );
}

export function KpiCards({ resumen }: { resumen: Resumen }) {
  return (
    <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
      <Kpi
        label="Artículos activos"
        value={formatNumber(resumen.total_articulos)}
        icon={<Boxes className="h-4 w-4" />}
        tone="text-muted-foreground"
      />
      <Kpi
        label="Bajo punto de pedido"
        value={formatNumber(resumen.bajo_punto_pedido)}
        icon={<PackageX className="h-4 w-4" />}
        tone="text-amber-600"
      />
      <Kpi
        label="Margen bajo"
        value={formatNumber(resumen.margen_bajo)}
        icon={<TrendingDown className="h-4 w-4" />}
        tone="text-destructive"
      />
      <Kpi
        label="Valor de stock"
        value={formatMoney(resumen.valor_stock)}
        icon={<Wallet className="h-4 w-4" />}
        tone="text-muted-foreground"
      />
    </div>
  );
}
