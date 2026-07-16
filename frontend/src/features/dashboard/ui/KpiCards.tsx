import { Boxes, PackageX, TrendingDown, Wallet } from "lucide-react";
import type { ReactNode } from "react";

import { cn } from "@/shared/lib/cn";
import { formatMoney, formatNumber } from "@/shared/lib/format";
import { Card } from "@/shared/ui/card";

import type { Resumen } from "../schema";

type Tone = "neutral" | "primary" | "warning" | "danger";

const CHIP: Record<Tone, string> = {
  neutral: "bg-muted text-muted-foreground",
  primary: "bg-primary/10 text-primary",
  warning: "bg-warning/15 text-warning",
  danger: "bg-destructive/10 text-destructive",
};

const BAR: Record<Tone, string> = {
  neutral: "bg-muted-foreground/40",
  primary: "bg-primary",
  warning: "bg-warning",
  danger: "bg-destructive",
};

function Stat({
  label,
  value,
  icon,
  tone,
  pct,
  caption,
}: {
  label: string;
  value: ReactNode;
  icon: ReactNode;
  tone: Tone;
  /** Proporción real 0–100. Si se omite, la card no muestra barra (no hay proporción que mostrar). */
  pct?: number;
  caption: string;
}) {
  return (
    <Card className="flex h-full flex-col gap-3 p-4">
      <div className="flex items-start justify-between gap-2">
        <span className="text-xs text-muted-foreground">{label}</span>
        <span
          className={cn(
            "flex h-9 w-9 shrink-0 items-center justify-center rounded-lg",
            CHIP[tone],
          )}
        >
          {icon}
        </span>
      </div>
      <p className="text-2xl font-semibold leading-none tabular-nums">{value}</p>
      <div className="mt-auto space-y-1.5">
        {pct !== undefined && (
          <div className="h-1.5 w-full overflow-hidden rounded-full bg-muted">
            <div
              className={cn("h-full rounded-full transition-all", BAR[tone])}
              style={{ width: `${Math.min(100, Math.max(0, pct))}%` }}
            />
          </div>
        )}
        <p className="text-xs text-muted-foreground">{caption}</p>
      </div>
    </Card>
  );
}

export function KpiCards({ resumen }: { resumen: Resumen }) {
  const total = resumen.total_articulos || 1;
  const pctBajo = Math.round((resumen.bajo_punto_pedido / total) * 100);
  const pctMargen = Math.round((resumen.margen_bajo / total) * 100);

  return (
    <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-4">
      <Stat
        label="Artículos activos"
        value={formatNumber(resumen.total_articulos)}
        icon={<Boxes className="h-5 w-5" />}
        tone="primary"
        caption="en el catálogo"
      />
      <Stat
        label="Bajo punto de pedido"
        value={formatNumber(resumen.bajo_punto_pedido)}
        icon={<PackageX className="h-5 w-5" />}
        tone="warning"
        pct={pctBajo}
        caption={`${pctBajo}% del catálogo a reponer`}
      />
      <Stat
        label="Margen bajo"
        value={formatNumber(resumen.margen_bajo)}
        icon={<TrendingDown className="h-5 w-5" />}
        tone="danger"
        pct={pctMargen}
        caption={`${pctMargen}% por debajo del objetivo`}
      />
      <Stat
        label="Valor de stock"
        value={formatMoney(resumen.valor_stock)}
        icon={<Wallet className="h-5 w-5" />}
        tone="neutral"
        caption="a precio de costo"
      />
    </div>
  );
}
