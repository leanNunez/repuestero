import { getRouteApi } from "@tanstack/react-router";
import { Search } from "lucide-react";
import { useState } from "react";

import { ArticuloTable } from "@/entities/articulo/ArticuloTable";
import { useCatalogo } from "@/features/catalogo-search/model/hooks";
import { Skeleton } from "@/shared/ui/skeleton";
import { EmptyState, ErrorState } from "@/shared/ui/states";

const route = getRouteApi("/catalogo");

function opciones(values: (string | null)[]): string[] {
  return [...new Set(values.filter((v): v is string => Boolean(v)))].sort((a, b) =>
    a.localeCompare(b, "es"),
  );
}

const selectClass =
  "h-9 rounded-md border border-input bg-background px-3 text-sm text-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 focus-visible:ring-offset-background disabled:opacity-50";

export function CatalogoPage() {
  const { q } = route.useSearch();
  const navigate = route.useNavigate();
  const { data, isLoading, isError, refetch } = useCatalogo(q);
  const [marca, setMarca] = useState("");
  const [rubro, setRubro] = useState("");

  const items = data ?? [];
  const marcas = opciones(items.map((i) => i.marca));
  const rubros = opciones(items.map((i) => i.rubro));
  const filtrados = items.filter(
    (i) => (!marca || i.marca === marca) && (!rubro || i.rubro === rubro),
  );

  return (
    <div className="mx-auto max-w-6xl space-y-4 p-4 md:p-5">
      <div className="flex flex-col gap-3 sm:flex-row sm:items-center">
        <div className="relative flex-1">
          <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
          <input
            value={q}
            onChange={(e) => navigate({ search: { q: e.target.value }, replace: true })}
            placeholder="Buscar por código, detalle, marca… (probá 'filtro para el gol')"
            className="h-9 w-full rounded-md border border-input bg-background pl-10 pr-3 text-sm focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 focus-visible:ring-offset-background"
            aria-label="Buscar en el catálogo"
          />
        </div>
        <div className="flex gap-2">
          <select
            value={marca}
            onChange={(e) => setMarca(e.target.value)}
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
          <select
            value={rubro}
            onChange={(e) => setRubro(e.target.value)}
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
      ) : filtrados.length === 0 ? (
        <EmptyState
          title="Sin resultados"
          hint={
            q || marca || rubro
              ? "No hay artículos que coincidan con la búsqueda o los filtros."
              : "No hay artículos cargados."
          }
        />
      ) : (
        <>
          <p className="text-xs text-muted-foreground">
            {filtrados.length} {filtrados.length === 1 ? "artículo" : "artículos"}
          </p>
          <ArticuloTable articulos={filtrados} />
        </>
      )}
    </div>
  );
}
