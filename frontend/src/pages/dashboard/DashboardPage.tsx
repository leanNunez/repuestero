import { Bot, PackageX, Sparkles, TrendingDown } from "lucide-react";
import type { ReactNode } from "react";

import { useDrawerStore } from "@/features/ui-shell/drawerStore";
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

function TableSkeleton() {
  return (
    <div className="space-y-2 p-4">
      {Array.from({ length: 5 }).map((_, i) => (
        <Skeleton key={i} className="h-10 w-full" />
      ))}
    </div>
  );
}

function AssistantLauncher({ onOpen }: { onOpen: () => void }) {
  return (
    <button
      onClick={onOpen}
      className="group flex w-full items-center gap-3 rounded-lg border border-border bg-accent px-4 py-3 text-left transition-colors hover:bg-accent/70 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 focus-visible:ring-offset-background active:scale-[0.99]"
    >
      <span className="flex h-9 w-9 shrink-0 items-center justify-center rounded-md bg-primary text-primary-foreground">
        <Bot className="h-5 w-5" />
      </span>
      <div className="min-w-0 flex-1">
        <p className="text-sm font-medium text-accent-foreground">Preguntá sobre tu negocio</p>
        <p className="truncate text-xs text-accent-foreground/70">
          “¿qué artículos tengo que reponer?”, “¿cuáles pierdo plata?” — en lenguaje natural
        </p>
      </div>
      <Sparkles className="h-4 w-4 shrink-0 text-primary transition-transform group-hover:scale-110" />
    </button>
  );
}

export function DashboardPage() {
  const resumen = useResumen();
  const reposicion = useReposicion();
  const margenes = useMargenes();
  const toggleAssistant = useDrawerStore((s) => s.toggleAssistant);
  const margenesBajos = (margenes.data ?? []).filter((m) => m.bajo);

  return (
    <div className="flex h-full flex-col gap-4 p-4 md:p-5">
      <AssistantLauncher onOpen={toggleAssistant} />

      {resumen.isLoading ? (
        <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-4">
          {Array.from({ length: 4 }).map((_, i) => (
            <Skeleton key={i} className="h-[74px] w-full" />
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
