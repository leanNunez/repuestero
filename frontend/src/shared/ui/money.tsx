import { cn } from "@/shared/lib/cn";
import { formatMoney, formatMoneyCentavos } from "@/shared/lib/format";

interface Props {
  value: number | string | null | undefined;
  /** Mostrar centavos: caja, cuenta corriente y comprobantes. Los listados van sin. */
  centavos?: boolean;
  className?: string;
}

/** La "columna de plata" (docs/art-direction.md): todo importe va en la Mono con cifras
 *  tabulares, para que una columna de números cierre como planilla de mostrador.
 *  Vacío = "—", nunca en blanco: un blanco se lee como dato perdido. */
export function Money({ value, centavos = false, className }: Props) {
  if (value === null || value === undefined || value === "") {
    return <span className="text-muted-foreground">—</span>;
  }

  const n = typeof value === "string" ? Number(value) : value;
  if (!Number.isFinite(n)) return <span className={className}>{String(value)}</span>;

  return (
    <span className={cn("font-mono tabular-nums", className)}>
      {centavos ? formatMoneyCentavos(n) : formatMoney(n)}
    </span>
  );
}
