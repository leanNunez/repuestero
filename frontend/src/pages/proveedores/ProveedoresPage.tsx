import { getRouteApi } from "@tanstack/react-router";
import { Search } from "lucide-react";
import { useEffect } from "react";

import { ProveedorTable } from "@/entities/proveedor/ProveedorTable";
import { PAGE_SIZE } from "@/features/proveedores/model/estado";
import { useCrearProveedor, useProveedores } from "@/features/proveedores/model/hooks";
import { FormularioProveedor } from "@/features/proveedores/ui/FormularioProveedor";
import { PageHeader } from "@/shared/ui/page-header";
import { Pagination } from "@/shared/ui/pagination";
import { QueryState } from "@/shared/ui/query-state";

const route = getRouteApi("/proveedores");

export function ProveedoresPage() {
  const { q, page } = route.useSearch();
  const navigate = route.useNavigate();

  const query = useProveedores(q, page);
  const crear = useCrearProveedor();

  const items = query.data?.items ?? [];
  const total = query.data?.total ?? 0;

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
      <PageHeader
        title="Proveedores"
        description="Padrón de proveedores. Los que llegan por un remito escaneado entran con el código del papel; los que se dan de alta acá los numera el sistema."
      />

      <FormularioProveedor
        cargando={crear.isPending}
        error={crear.error?.message ?? null}
        ultimoCodigo={crear.data?.codigo ?? null}
        // Después del alta, el padrón salta a buscar el proveedor recién creado. Sin esto te dice
        // "PRV-000008" y te deja mirando la página 1 del abecedario, donde casi nunca está.
        onCrear={(v) => crear.mutate(v, { onSuccess: (p) => setSearch({ q: p.codigo, page: 1 }) })}
      />

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

      <QueryState
        query={query}
        isEmpty={(d) => d.items.length === 0}
        empty={{
          title: q ? "Sin resultados" : "Sin proveedores",
          hint: q
            ? "No hay proveedores que coincidan con la búsqueda."
            : "Todavía no hay proveedores cargados.",
        }}
      >
        {(d) => (
          <>
            {/* Con una búsqueda activa el sustantivo cambia: "80 proveedores" sobre un padrón de 900
                se lee como el tamaño del padrón, no como el del resultado. */}
            <p className="text-xs text-muted-foreground">
              {q
                ? `${d.total} ${d.total === 1 ? "resultado" : "resultados"}`
                : `${d.total} ${d.total === 1 ? "proveedor" : "proveedores"}`}
            </p>
            <ProveedorTable proveedores={d.items} />
            <Pagination
              page={page}
              pageSize={PAGE_SIZE}
              total={d.total}
              onPageChange={(p) => setSearch({ page: p })}
            />
          </>
        )}
      </QueryState>
    </div>
  );
}
