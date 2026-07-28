import { getRouteApi } from "@tanstack/react-router";
import { Search } from "lucide-react";
import { useEffect } from "react";

import { ClienteTable } from "@/entities/cliente/ClienteTable";
import { PAGE_SIZE } from "@/features/clientes/model/estado";
import { useClientes, useCrearCliente } from "@/features/clientes/model/hooks";
import { FormularioCliente } from "@/features/clientes/ui/FormularioCliente";
import { Pagination } from "@/shared/ui/pagination";
import { Skeleton } from "@/shared/ui/skeleton";
import { EmptyState, ErrorState } from "@/shared/ui/states";

const route = getRouteApi("/clientes");

export function ClientesPage() {
  const { q, page } = route.useSearch();
  const navigate = route.useNavigate();

  const { data, isLoading, isError, refetch } = useClientes(q, page);
  const crear = useCrearCliente();

  const items = data?.items ?? [];
  const total = data?.total ?? 0;

  const setSearch = (patch: Partial<{ q: string; page: number }>) =>
    navigate({ search: (prev) => ({ ...prev, ...patch }), replace: true });

  // Página fuera de rango (URL compartida, o una búsqueda que achica el resultado estando en la
  // página 4): volver a la 1. Sin esto la tabla queda vacía sobre un padrón que tiene datos.
  useEffect(() => {
    if (total > 0 && items.length === 0 && page > 1) setSearch({ page: 1 });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [total, items.length, page]);

  return (
    <div className="mx-auto max-w-6xl space-y-4 p-4 md:p-5">
      <p className="text-sm text-muted-foreground">
        Padrón de clientes. El código lo asigna el sistema al dar de alta.
      </p>

      <FormularioCliente
        cargando={crear.isPending}
        error={crear.error?.message ?? null}
        ultimoCodigo={crear.data?.codigo ?? null}
        // Después del alta, el padrón salta a buscar el cliente recién creado. Es el cierre del
        // circuito: sin esto te dice "CLI-000008" y te deja mirando la página 1 del abecedario,
        // donde el que acabás de cargar casi nunca está.
        onCrear={(v) =>
          crear.mutate(v, { onSuccess: (c) => setSearch({ q: c.codigo, page: 1 }) })
        }
      />

      <div className="relative">
        <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
        <input
          value={q}
          onChange={(e) => setSearch({ q: e.target.value, page: 1 })}
          placeholder="Buscar por denominación, código o CUIT…"
          className="h-9 w-full rounded-md border border-input bg-background pl-10 pr-3 text-sm focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 focus-visible:ring-offset-background"
          aria-label="Buscar clientes"
        />
      </div>

      {isLoading ? (
        <div className="space-y-2">
          {Array.from({ length: 6 }).map((_, i) => (
            <Skeleton key={i} className="h-11 w-full" />
          ))}
        </div>
      ) : isError ? (
        <ErrorState onRetry={() => void refetch()} />
      ) : items.length === 0 ? (
        <EmptyState
          title={q ? "Sin resultados" : "Sin clientes"}
          hint={
            q
              ? "No hay clientes que coincidan con la búsqueda."
              : "Todavía no hay clientes cargados."
          }
        />
      ) : (
        <>
          <p className="text-xs text-muted-foreground">
            {total} {total === 1 ? "cliente" : "clientes"}
          </p>
          <ClienteTable clientes={items} />
          <Pagination
            page={page}
            pageSize={PAGE_SIZE}
            total={total}
            onPageChange={(p) => setSearch({ page: p })}
          />
        </>
      )}
    </div>
  );
}
