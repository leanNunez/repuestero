import { getRouteApi } from "@tanstack/react-router";
import { useEffect } from "react";

import { ClienteTable } from "@/entities/cliente/ClienteTable";
import { PAGE_SIZE } from "@/features/clientes/model/estado";
import { useClientes, useCrearCliente } from "@/features/clientes/model/hooks";
import { FormularioCliente } from "@/features/clientes/ui/FormularioCliente";
import { PageHeader } from "@/shared/ui/page-header";
import { Pagination } from "@/shared/ui/pagination";
import { QueryState } from "@/shared/ui/query-state";
import { SearchInput } from "@/shared/ui/search-input";

const route = getRouteApi("/clientes");

export function ClientesPage() {
  const { q, page } = route.useSearch();
  const navigate = route.useNavigate();

  const query = useClientes(q, page);
  const crear = useCrearCliente();

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
        title="Clientes"
        description="Padrón de clientes. El código lo asigna el sistema al dar de alta."
      />

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

      <SearchInput
        value={q}
        onChange={(e) => setSearch({ q: e.target.value, page: 1 })}
        placeholder="Buscar por denominación, código o CUIT…"
        aria-label="Buscar clientes"
      />

      <QueryState
        query={query}
        isEmpty={(d) => d.items.length === 0}
        empty={{
          title: q ? "Sin resultados" : "Sin clientes",
          hint: q
            ? "No hay clientes que coincidan con la búsqueda."
            : "Todavía no hay clientes cargados.",
        }}
      >
        {(d) => (
          <>
            {/* Con una búsqueda activa el sustantivo cambia: "80 clientes" sobre un padrón de 900
                se lee como el tamaño del padrón, no como el tamaño del resultado. Mismo criterio
                que el catálogo. */}
            <p className="text-xs text-muted-foreground">
              {q
                ? `${d.total} ${d.total === 1 ? "resultado" : "resultados"}`
                : `${d.total} ${d.total === 1 ? "cliente" : "clientes"}`}
            </p>
            <ClienteTable clientes={d.items} />
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
