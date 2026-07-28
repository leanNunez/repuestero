import { getRouteApi } from "@tanstack/react-router";
import { Search } from "lucide-react";
import { useEffect } from "react";

import { ProveedorTable } from "@/entities/proveedor/ProveedorTable";
import { PAGE_SIZE } from "@/features/proveedores/model/estado";
import { useProveedores } from "@/features/proveedores/model/hooks";
import { Pagination } from "@/shared/ui/pagination";
import { Skeleton } from "@/shared/ui/skeleton";
import { EmptyState, ErrorState } from "@/shared/ui/states";

const route = getRouteApi("/proveedores");

export function ProveedoresPage() {
  const { q, page } = route.useSearch();
  const navigate = route.useNavigate();

  const { data, isLoading, isError, refetch } = useProveedores(q, page);

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
        Padrón de proveedores. Los que llegan por un remito escaneado entran con el código del
        papel; los que se dan de alta acá los numera el sistema.
      </p>

      <div className="relative">
        <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
        <input
          value={q}
          onChange={(e) => setSearch({ q: e.target.value, page: 1 })}
          placeholder="Buscar por razón social, código o CUIT…"
          className="h-9 w-full rounded-md border border-input bg-background pl-10 pr-3 text-sm focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 focus-visible:ring-offset-background"
          aria-label="Buscar proveedores"
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
          title={q ? "Sin resultados" : "Sin proveedores"}
          hint={
            q
              ? "No hay proveedores que coincidan con la búsqueda."
              : "Todavía no hay proveedores cargados."
          }
        />
      ) : (
        <>
          {/* Con una búsqueda activa el sustantivo cambia: "80 proveedores" sobre un padrón de 900
              se lee como el tamaño del padrón, no como el del resultado. */}
          <p className="text-xs text-muted-foreground">
            {q
              ? `${total} ${total === 1 ? "resultado" : "resultados"}`
              : `${total} ${total === 1 ? "proveedor" : "proveedores"}`}
          </p>
          <ProveedorTable proveedores={items} />
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
