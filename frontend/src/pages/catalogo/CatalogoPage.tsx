import { getRouteApi } from "@tanstack/react-router";
import { Search } from "lucide-react";

import { ArticuloTable } from "@/entities/articulo/ArticuloTable";
import { useCatalogo } from "@/features/catalogo-search/model/hooks";
import { Skeleton } from "@/shared/ui/skeleton";
import { EmptyState, ErrorState } from "@/shared/ui/states";

const route = getRouteApi("/catalogo");

export function CatalogoPage() {
  const { q } = route.useSearch();
  const navigate = route.useNavigate();
  const { data, isLoading, isError, refetch } = useCatalogo(q);

  return (
    <div className="mx-auto max-w-5xl space-y-4">
      <div className="relative">
        <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
        <input
          value={q}
          onChange={(e) => navigate({ search: { q: e.target.value }, replace: true })}
          placeholder="Buscar por código, detalle, marca… (probá 'filtro para el gol')"
          className="h-11 w-full rounded-lg border border-input bg-background pl-10 pr-3 text-sm focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 focus-visible:ring-offset-background"
          aria-label="Buscar en el catálogo"
        />
      </div>

      {isLoading ? (
        <div className="space-y-2">
          {Array.from({ length: 6 }).map((_, i) => (
            <Skeleton key={i} className="h-12 w-full" />
          ))}
        </div>
      ) : isError ? (
        <ErrorState onRetry={() => void refetch()} />
      ) : !data || data.length === 0 ? (
        <EmptyState
          title="Sin resultados"
          hint={q ? `No encontramos nada para "${q}".` : "No hay artículos cargados."}
        />
      ) : (
        <ArticuloTable articulos={data} />
      )}
    </div>
  );
}
