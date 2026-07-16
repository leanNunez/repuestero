import { Boxes, PackageX, TrendingDown, Wallet } from "lucide-react";
import type { ReactNode } from "react";

import { cn } from "@/shared/lib/cn";
import { formatMoney, formatNumber } from "@/shared/lib/format";
import { Card } from "@/shared/ui/card";

import type { Resumen } from "../schema";

type Tone = "neutral" | "primary" | "warning" | "danger";

const TONE_CHIP: Record<Tone, string> = {
  neutral: "bg-muted text-muted-foreground",
  primary: "bg-primary/10 text-primary",
  warning: "bg-warning/15 text-warning",
  danger: "bg-destructive/10 text-destructive",
};

function Kpi({
  label,
  value,
  icon,
  tone,
}: {
  label: string;
  value: ReactNode;
  icon: ReactNode;
  tone: Tone;
}) {
  return (
    <Card className="flex items-center gap-3 p-4">
      <span
        className={cn(
          "flex h-10 w-10 shrink-0 items-center justify-center rounded-lg",
          TONE_CHIP[tone],
        )}
      >
        {icon}
      </span>
      <div className="min-w-0">
        <p className="truncate text-xs text-muted-foreground">{label}</p>
        <p className="text-2xl font-semibold tabular-nums leading-tight">{value}</p>
      </div>
    </Card>
  );
}

export function KpiCards({ resumen }: { resumen: Resumen }) {
  return (
    <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-4">
      <Kpi
        label="Artículos activos"
        value={formatNumber(resumen.total_articulos)}
        icon={<Boxes className="h-5 w-5" />}
        tone="primary"
      />
      <Kpi
        label="Bajo punto de pedido"
        value={formatNumber(resumen.bajo_punto_pedido)}
        icon={<PackageX className="h-5 w-5" />}
        tone="warning"
      />
      <Kpi
        label="Margen bajo"
        value={formatNumber(resumen.margen_bajo)}
        icon={<TrendingDown className="h-5 w-5" />}
        tone="danger"
      />
      <Kpi
        label="Valor de stock"
        value={formatMoney(resumen.valor_stock)}
        icon={<Wallet className="h-5 w-5" />}
        tone="neutral"
      />
    </div>
  );
}
