import { getRouteApi } from "@tanstack/react-router";
import { Search } from "lucide-react";
import { useEffect } from "react";

import { ArticuloTable } from "@/entities/articulo/ArticuloTable";
import {
  PAGE_SIZE,
  useCatalogo,
  useMarcas,
  useRubros,
} from "@/features/catalogo-search/model/hooks";
import { Pagination } from "@/shared/ui/pagination";
import { Skeleton } from "@/shared/ui/skeleton";
import { EmptyState, ErrorState } from "@/shared/ui/states";

const route = getRouteApi("/catalogo");

const selectClass =
  "h-9 rounded-md border border-input bg-background px-3 text-sm text-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 focus-visible:ring-offset-background disabled:opacity-50";

export function CatalogoPage() {
  const { q, page, rubro, marca } = route.useSearch();
  const navigate = route.useNavigate();

  const { data, isLoading, isError, refetch } = useCatalogo(q, page, rubro, marca);
  const { data: rubros = [] } = useRubros();
  const { data: marcas = [] } = useMarcas();

  const buscando = q.trim().length > 0;
  const items = data?.items ?? [];
  const total = data?.total ?? 0;

  // En listado, rubro/marca ya filtran server-side. En búsqueda, la API devuelve un conjunto
  // acotado (<=30) sin filtrar: aplicamos rubro/marca en el cliente sobre esos resultados.
  const visibles = buscando
    ? items.filter((i) => (!rubro || i.rubro === rubro) && (!marca || i.marca === marca))
    : items;

  const setSearch = (patch: Partial<{ q: string; page: number; rubro: string; marca: string }>) =>
    navigate({ search: (prev) => ({ ...prev, ...patch }), replace: true });

  // Página fuera de rango (URL manipulada o filtro que achica el resultado): volver a la 1.
  useEffect(() => {
    if (!buscando && total > 0 && items.length === 0 && page > 1) setSearch({ page: 1 });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [buscando, total, items.length, page]);

  return (
    <div className="mx-auto max-w-6xl space-y-4 p-4 md:p-5">
      <div className="flex flex-col gap-3 sm:flex-row sm:items-center">
        <div className="relative flex-1">
          <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
          <input
            value={q}
            onChange={(e) => setSearch({ q: e.target.value, page: 1 })}
            placeholder="Buscar por código, detalle, marca… (probá 'filtro para el gol')"
            className="h-9 w-full rounded-md border border-input bg-background pl-10 pr-3 text-sm focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 focus-visible:ring-offset-background"
            aria-label="Buscar en el catálogo"
          />
        </div>
        <div className="flex gap-2">
          <select
            value={rubro}
            onChange={(e) => setSearch({ rubro: e.target.value, page: 1 })}
            className={selectClass}
            aria-label="Filtrar por rubro"
            disabled={rubros.length === 0}
          >
            <option value="">Todos los rubros</option>
            {rubros.map((r) => (
              <option key={r} value={r}>
                {r}
              </option>
            ))}
          </select>
          <select
            value={marca}
            onChange={(e) => setSearch({ marca: e.target.value, page: 1 })}
            className={selectClass}
            aria-label="Filtrar por marca"
            disabled={marcas.length === 0}
          >
            <option value="">Todas las marcas</option>
            {marcas.map((m) => (
              <option key={m} value={m}>
                {m}
              </option>
            ))}
          </select>
        </div>
      </div>

      {isLoading ? (
        <div className="space-y-2">
          {Array.from({ length: 8 }).map((_, i) => (
            <Skeleton key={i} className="h-11 w-full" />
          ))}
        </div>
      ) : isError ? (
        <ErrorState onRetry={() => void refetch()} />
      ) : visibles.length === 0 ? (
        <EmptyState
          title="Sin resultados"
          hint={
            q || rubro || marca
              ? "No hay artículos que coincidan con la búsqueda o los filtros."
              : "No hay artículos cargados."
          }
        />
      ) : (
        <>
          <p className="text-xs text-muted-foreground">
            {buscando
              ? `${visibles.length} ${visibles.length === 1 ? "resultado" : "resultados"}`
              : `${total} ${total === 1 ? "artículo" : "artículos"}`}
          </p>
          <ArticuloTable articulos={visibles} />
          {!buscando && (
            <Pagination
              page={page}
              pageSize={PAGE_SIZE}
              total={total}
              onPageChange={(p) => setSearch({ page: p })}
            />
          )}
        </>
      )}
    </div>
  );
}
