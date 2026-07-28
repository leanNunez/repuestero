import { ClienteTable } from "@/entities/cliente/ClienteTable";
import { useClientes, useCrearCliente } from "@/features/clientes/model/hooks";
import { FormularioCliente } from "@/features/clientes/ui/FormularioCliente";
import { Skeleton } from "@/shared/ui/skeleton";
import { EmptyState, ErrorState } from "@/shared/ui/states";

export function ClientesPage() {
  const { data, isLoading, isError, refetch } = useClientes();
  const crear = useCrearCliente();

  return (
    <div className="mx-auto max-w-6xl space-y-4 p-4 md:p-5">
      <p className="text-sm text-muted-foreground">
        Padrón de clientes. El código lo asigna el sistema al dar de alta.
      </p>

      <FormularioCliente
        cargando={crear.isPending}
        error={crear.error?.message ?? null}
        ultimoCodigo={crear.data?.codigo ?? null}
        onCrear={(v) => crear.mutate(v)}
      />

      {isLoading ? (
        <div className="space-y-2">
          {Array.from({ length: 6 }).map((_, i) => (
            <Skeleton key={i} className="h-11 w-full" />
          ))}
        </div>
      ) : isError ? (
        <ErrorState onRetry={() => void refetch()} />
      ) : !data || data.length === 0 ? (
        <EmptyState title="Sin clientes" hint="Todavía no hay clientes cargados." />
      ) : (
        <>
          <p className="text-xs text-muted-foreground">
            {data.length} {data.length === 1 ? "cliente" : "clientes"}
          </p>
          <ClienteTable clientes={data} />
        </>
      )}
    </div>
  );
}
