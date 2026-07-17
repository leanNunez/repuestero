import { getRouteApi, Link } from "@tanstack/react-router";
import { ArrowLeft } from "lucide-react";

import { useArticulo } from "@/features/catalogo-search/model/hooks";
import { formatMoney, formatNumber } from "@/shared/lib/format";
import { Card } from "@/shared/ui/card";
import { Skeleton } from "@/shared/ui/skeleton";
import { ErrorState } from "@/shared/ui/states";

const route = getRouteApi("/catalogo/$codigo");

function Dato({ label, valor }: { label: string; valor: string }) {
  return (
    <div>
      <dt className="text-xs text-muted-foreground">{label}</dt>
      <dd className="font-medium tabular-nums">{valor}</dd>
    </div>
  );
}

export function ArticuloPage() {
  const { codigo } = route.useParams();
  const { data, isLoading, isError, refetch } = useArticulo(codigo);

  return (
    <div className="mx-auto max-w-2xl space-y-4">
      <Link
        to="/catalogo"
        search={{ q: "" }}
        className="inline-flex items-center gap-1 text-sm text-muted-foreground hover:text-foreground"
      >
        <ArrowLeft className="h-4 w-4" />
        Volver al catálogo
      </Link>

      {isLoading ? (
        <Skeleton className="h-48 w-full" />
      ) : isError || !data ? (
        <ErrorState onRetry={() => void refetch()} />
      ) : (
        <Card className="space-y-4 p-6">
          <div>
            <h2 className="text-lg font-semibold">{data.detalle}</h2>
            <p className="text-sm text-muted-foreground">{data.codigo}</p>
          </div>
          <dl className="grid grid-cols-2 gap-4 text-sm">
            <Dato label="Costo" valor={formatMoney(data.costo)} />
            <Dato label="IVA" valor={`${formatNumber(data.alicuota_iva)}%`} />
            <Dato label="Punto de pedido" valor={formatNumber(data.punto_pedido)} />
            <Dato label="Marca" valor={data.marca ?? "—"} />
            <Dato label="Rubro" valor={data.rubro ?? "—"} />
          </dl>
        </Card>
      )}
    </div>
  );
}
