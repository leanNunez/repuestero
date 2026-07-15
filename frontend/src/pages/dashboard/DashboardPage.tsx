import type { ReactNode } from "react";

import {
  useMargenes,
  useReposicion,
  useResumen,
} from "@/features/dashboard/model/hooks";
import { KpiCards } from "@/features/dashboard/ui/KpiCards";
import { MargenesTable } from "@/features/dashboard/ui/MargenesTable";
import { ReposicionTable } from "@/features/dashboard/ui/ReposicionTable";
import { Skeleton } from "@/shared/ui/skeleton";
import { EmptyState, ErrorState } from "@/shared/ui/states";

function Section({
  title,
  subtitle,
  children,
}: {
  title: string;
  subtitle?: string;
  children: ReactNode;
}) {
  return (
    <section className="space-y-3">
      <div>
        <h2 className="text-sm font-semibold">{title}</h2>
        {subtitle && <p className="text-xs text-muted-foreground">{subtitle}</p>}
      </div>
      {children}
    </section>
  );
}

function TableSkeleton() {
  return (
    <div className="space-y-2">
      {Array.from({ length: 4 }).map((_, i) => (
        <Skeleton key={i} className="h-11 w-full" />
      ))}
    </div>
  );
}

export function DashboardPage() {
  const resumen = useResumen();
  const reposicion = useReposicion();
  const margenes = useMargenes();
  const margenesBajos = (margenes.data ?? []).filter((m) => m.bajo);

  return (
    <div className="mx-auto max-w-6xl space-y-8">
      <Section title="Resumen">
        {resumen.isLoading ? (
          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
            {Array.from({ length: 4 }).map((_, i) => (
              <Skeleton key={i} className="h-24 w-full" />
            ))}
          </div>
        ) : resumen.isError || !resumen.data ? (
          <ErrorState onRetry={() => void resumen.refetch()} />
        ) : (
          <KpiCards resumen={resumen.data} />
        )}
      </Section>

      <Section title="Reposición" subtitle="Artículos que llegaron a su punto de pedido">
        {reposicion.isLoading ? (
          <TableSkeleton />
        ) : reposicion.isError ? (
          <ErrorState onRetry={() => void reposicion.refetch()} />
        ) : !reposicion.data || reposicion.data.length === 0 ? (
          <EmptyState title="Todo con stock" hint="Ningún artículo bajo el punto de pedido." />
        ) : (
          <ReposicionTable items={reposicion.data} />
        )}
      </Section>

      <Section
        title="Guardián de márgenes"
        subtitle="Artículos que se venden bajo el margen objetivo (20%)"
      >
        {margenes.isLoading ? (
          <TableSkeleton />
        ) : margenes.isError ? (
          <ErrorState onRetry={() => void margenes.refetch()} />
        ) : margenesBajos.length === 0 ? (
          <EmptyState title="Márgenes sanos" hint="Ningún artículo por debajo del objetivo." />
        ) : (
          <MargenesTable items={margenesBajos} />
        )}
      </Section>
    </div>
  );
}
