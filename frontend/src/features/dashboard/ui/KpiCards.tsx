import { Boxes, PackageX, TrendingDown, Wallet } from "lucide-react";
import type { ReactNode } from "react";

import { cn } from "@/shared/lib/cn";
import { formatMoney, formatMoneyCompacto, formatNumber } from "@/shared/lib/format";

import type { Resumen } from "../schema";

type Tone = "neutral" | "primary" | "warning" | "danger";

/** El tono vive SOLO en la barra de proporción. Los chips pastel detrás del ícono se
 *  fueron: el arquetipo de herramienta densa los desaconseja explícitamente, y encima
 *  metían cuatro manchas de color compitiendo con los números, que son lo que importa. */
const BAR: Record<Tone, string> = {
  neutral: "bg-muted-foreground/40",
  primary: "bg-primary",
  warning: "bg-warning",
  danger: "bg-destructive",
};

function Celda({
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
  /** Proporción real 0–100. Si se omite, la celda no muestra barra (no hay proporción que mostrar). */
  pct?: number;
  caption: string;
}) {
  return (
    <div className="flex flex-col gap-2 px-4 py-4">
      <div className="flex items-center gap-1.5 text-muted-foreground">
        {icon}
        <span className="text-[11px] font-medium uppercase tracking-wide">{label}</span>
      </div>

      {/* El número es el héroe: 44px contra 14px de body = 3,1×. En mono, para que las
          cuatro cifras de la franja compartan el ancho de dígito y se lean como una fila. */}
      <p className="font-mono text-4xl font-semibold tabular-nums">{value}</p>

      <div className="mt-auto space-y-1.5">
        {pct !== undefined && (
          <div className="h-1 w-full overflow-hidden rounded-full bg-muted">
            <div
              className={cn("h-full rounded-full transition-[width]", BAR[tone])}
              style={{ width: `${Math.min(100, Math.max(0, pct))}%` }}
            />
          </div>
        )}
        <p className="text-xs text-muted-foreground">{caption}</p>
      </div>
    </div>
  );
}

/** Franja de datos a ancho completo, dividida por líneas — NO una grilla de cards.
 *
 * El arquetipo de herramienta densa pide "tablas sobre cards" y tiene como firma las
 * líneas de grilla visibles con cifras monoespaciadas; su anti-patrón declarado son las
 * cards redondeadas con chips pastel, que es exactamente lo que había acá. La franja
 * además deja los cuatro números alineados en una sola fila de lectura. */
export function KpiCards({ resumen }: { resumen: Resumen }) {
  const total = resumen.total_articulos || 1;
  const pctBajo = Math.round((resumen.bajo_punto_pedido / total) * 100);
  const pctMargen = Math.round((resumen.margen_bajo / total) * 100);
  const icono = "h-3.5 w-3.5 shrink-0";

  return (
    <div className="grid grid-cols-1 divide-y divide-border border-y border-border bg-card sm:grid-cols-2 sm:divide-x lg:grid-cols-4 lg:divide-y-0">
      <Celda
        label="Artículos activos"
        value={formatNumber(resumen.total_articulos)}
        icon={<Boxes className={icono} />}
        tone="primary"
        caption="en el catálogo"
      />
      <Celda
        label="Bajo punto de pedido"
        value={formatNumber(resumen.bajo_punto_pedido)}
        icon={<PackageX className={icono} />}
        tone="warning"
        pct={pctBajo}
        caption={`${pctBajo}% del catálogo a reponer`}
      />
      <Celda
        label="Margen bajo"
        value={formatNumber(resumen.margen_bajo)}
        icon={<TrendingDown className={icono} />}
        tone="danger"
        pct={pctMargen}
        caption={`${pctMargen}% por debajo del objetivo`}
      />
      <Celda
        label="Valor de stock"
        value={formatMoneyCompacto(resumen.valor_stock)}
        icon={<Wallet className={icono} />}
        tone="neutral"
        caption={`a precio de costo · ${formatMoney(resumen.valor_stock)}`}
      />
    </div>
  );
}
