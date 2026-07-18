import { LayoutDashboard, PackageX, TrendingDown } from "lucide-react";
import type { ReactNode } from "react";

import { AssistantLauncher } from "@/features/chat/ui/AssistantLauncher";
import {
  useMargenes,
  useReposicion,
  useResumen,
} from "@/features/dashboard/model/hooks";
import { KpiCards } from "@/features/dashboard/ui/KpiCards";
import { MargenesTable } from "@/features/dashboard/ui/MargenesTable";
import { ReposicionTable } from "@/features/dashboard/ui/ReposicionTable";
import { Badge } from "@/shared/ui/badge";
import { Card } from "@/shared/ui/card";
import { Skeleton } from "@/shared/ui/skeleton";
import { EmptyState, ErrorState } from "@/shared/ui/states";

/** Card con cabecera fija y cuerpo que scrollea internamente → la página nunca scrollea. */
function Panel({
  title,
  subtitle,
  icon,
  badge,
  children,
}: {
  title: string;
  subtitle: string;
  icon: ReactNode;
  badge?: ReactNode;
  children: ReactNode;
}) {
  return (
    <Card className="flex min-h-0 flex-col overflow-hidden">
      <div className="flex shrink-0 items-center gap-3 border-b border-border px-4 py-3">
        <span className="flex h-8 w-8 items-center justify-center rounded-md bg-muted text-muted-foreground">
          {icon}
        </span>
        <div className="min-w-0 flex-1">
          <h2 className="text-sm font-semibold">{title}</h2>
          <p className="truncate text-xs text-muted-foreground">{subtitle}</p>
        </div>
        {badge}
      </div>
      <div className="min-h-0 flex-1 overflow-y-auto">{children}</div>
    </Card>
  );
}

/** Fecha larga en es-AR, con la inicial en mayúscula ("Sábado 18 de julio"). */
function hoy(): string {
  const f = new Intl.DateTimeFormat("es-AR", {
    weekday: "long",
    day: "numeric",
    month: "long",
  }).format(new Date());
  return f.charAt(0).toUpperCase() + f.slice(1);
}

/** Cabecera de la página: le da identidad. Sin esto el dashboard no se anuncia como tal. */
function DashboardHeader() {
  return (
    <div className="flex items-center gap-3">
      <span className="flex h-11 w-11 shrink-0 items-center justify-center rounded-xl bg-primary/10 text-primary">
        <LayoutDashboard className="h-6 w-6" />
      </span>
      <div className="min-w-0">
        <h1 className="text-xl font-bold tracking-tight sm:text-2xl">Panel de control</h1>
        <p className="truncate text-sm text-muted-foreground">
          Tu negocio de un vistazo · {hoy()}
        </p>
      </div>
    </div>
  );
}

function TableSkeleton() {
  return (
    <div className="space-y-2 p-4">
      {Array.from({ length: 5 }).map((_, i) => (
        <Skeleton key={i} className="h-10 w-full" />
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
    <div className="flex h-full flex-col gap-4 p-4 md:p-5">
      <DashboardHeader />
      <AssistantLauncher />

      {resumen.isLoading ? (
        <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-4">
          {Array.from({ length: 4 }).map((_, i) => (
            <Skeleton key={i} className="h-[116px] w-full" />
          ))}
        </div>
      ) : resumen.isError || !resumen.data ? (
        <Card className="p-4">
          <ErrorState onRetry={() => void resumen.refetch()} />
        </Card>
      ) : (
        <KpiCards resumen={resumen.data} />
      )}

      <div className="grid min-h-0 flex-1 grid-cols-1 gap-4 lg:grid-cols-2">
        <Panel
          title="Reposición"
          subtitle="Artículos que llegaron a su punto de pedido"
          icon={<PackageX className="h-4 w-4" />}
          badge={
            reposicion.data?.length ? (
              <Badge variant="warning">{reposicion.data.length}</Badge>
            ) : undefined
          }
        >
          {reposicion.isLoading ? (
            <TableSkeleton />
          ) : reposicion.isError ? (
            <ErrorState onRetry={() => void reposicion.refetch()} />
          ) : !reposicion.data || reposicion.data.length === 0 ? (
            <EmptyState title="Todo con stock" hint="Ningún artículo bajo el punto de pedido." />
          ) : (
            <ReposicionTable items={reposicion.data} />
          )}
        </Panel>

        <Panel
          title="Guardián de márgenes"
          subtitle="Artículos que se venden bajo el margen objetivo (20%)"
          icon={<TrendingDown className="h-4 w-4" />}
          badge={
            margenesBajos.length ? (
              <Badge variant="danger">{margenesBajos.length}</Badge>
            ) : undefined
          }
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
        </Panel>
      </div>
    </div>
  );
}
