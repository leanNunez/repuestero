import { pesos } from "@/entities/remito/formato";
import type { VentaLeer } from "@/entities/venta/schema";
import { Card } from "@/shared/ui/card";
import { Skeleton } from "@/shared/ui/skeleton";
import { EmptyState, ErrorState } from "@/shared/ui/states";

function comprobante(v: VentaLeer): string {
  const numero = String(v.numero).padStart(8, "0");
  return `${v.tipo} ${String(v.pto_venta).padStart(4, "0")}-${numero}`;
}

interface Props {
  ventas: VentaLeer[] | undefined;
  isLoading: boolean;
  isError: boolean;
  onRetry: () => void;
}

export function ListadoVentas({ ventas, isLoading, isError, onRetry }: Props) {
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
  if (!ventas || ventas.length === 0) {
    return <EmptyState title="Todavía no emitiste ninguna venta" hint="Armá la primera arriba." />;
  }

  return (
    <Card className="divide-y overflow-hidden p-0">
      {ventas.map((v) => (
        <div key={v.id} className="flex items-center justify-between gap-3 p-3 text-sm">
          <div className="min-w-0">
            <p className="truncate font-medium tabular-nums">{comprobante(v)}</p>
            <p className="text-xs text-muted-foreground">
              {v.fecha} · {v.condicion === "cta_cte" ? "Cuenta corriente" : "Contado"}
            </p>
          </div>
          <span className="font-medium tabular-nums">{pesos(v.total)}</span>
        </div>
      ))}
    </Card>
  );
}
