import { pesos } from "@/entities/remito/formato";
import type { CompraLeer } from "@/entities/compra/schema";
import { cn } from "@/shared/lib/cn";
import { Card } from "@/shared/ui/card";
import { Skeleton } from "@/shared/ui/skeleton";
import { EmptyState, ErrorState } from "@/shared/ui/states";

interface Props {
  compras: CompraLeer[] | undefined;
  isLoading: boolean;
  isError: boolean;
  onRetry: () => void;
  /** Para que la columna de altura fija le dé el alto sobrante y scrollee solo la lista. */
  className?: string;
}

export function ListadoCompras({
  compras,
  isLoading,
  isError,
  onRetry,
  className,
}: Props) {
  if (isLoading) {
    return (
      <div className="space-y-2">
        {Array.from({ length: 5 }).map((_, i) => (
          <Skeleton key={i} className="h-12 w-full" />
        ))}
      </div>
    );
  }
  if (isError) return <ErrorState onRetry={onRetry} />;
  if (!compras || compras.length === 0) {
    return (
      <EmptyState title="Todavía no registraste ninguna compra" hint="Cargá la primera arriba." />
    );
  }

  return (
    <Card className={cn("divide-y overflow-hidden p-0", className)}>
      {compras.map((c) => (
        <div key={c.id} className="flex items-center justify-between gap-3 p-3 text-sm">
          <div className="min-w-0">
            <p className="truncate font-medium tabular-nums">{c.numero_comprobante}</p>
            <p className="text-xs text-muted-foreground">
              {c.fecha} · {c.condicion === "cta_cte" ? "Cuenta corriente" : "Contado"}
            </p>
          </div>
          <span className="font-medium tabular-nums">{pesos(c.total)}</span>
        </div>
      ))}
    </Card>
  );
}
