import { getRouteApi } from "@tanstack/react-router";
import { useEffect } from "react";

import { ArticuloTable } from "@/entities/articulo/ArticuloTable";
import { useCrearArticulo } from "@/features/catalogo-alta/model/hooks";
import { FormularioArticulo } from "@/features/catalogo-alta/ui/FormularioArticulo";
import {
  PAGE_SIZE,
  useCatalogo,
  useListasPrecio,
  useMarcas,
  useRubros,
} from "@/features/catalogo-search/model/hooks";
import { ApiError } from "@/shared/api/client";
import { NativeSelect } from "@/shared/ui/native-select";
import { PageHeader } from "@/shared/ui/page-header";
import { PageBody, PageLayout } from "@/shared/ui/page-layout";
import { Pagination } from "@/shared/ui/pagination";
import { SearchInput } from "@/shared/ui/search-input";
import { Skeleton } from "@/shared/ui/skeleton";
import { EmptyState, ErrorState } from "@/shared/ui/states";

const route = getRouteApi("/catalogo");

export function CatalogoPage() {
  const { q, page, rubro, marca } = route.useSearch();
  const navigate = route.useNavigate();

  const { data, isLoading, isError, refetch } = useCatalogo(q, page, rubro, marca);
  const { data: rubros = [] } = useRubros();
  const { data: marcas = [] } = useMarcas();
  const { data: listas = [] } = useListasPrecio();
  const crear = useCrearArticulo();

  // El 409 por código duplicado NO es un error del formulario: es un problema de UN campo, y va
  // debajo de ese campo. Al pie diría "ya existe" sin decir qué, con el código a diez centímetros.
  const codigoRepetido =
    crear.error instanceof ApiError && crear.error.status === 409 ? crear.error.detail : null;

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
    <PageLayout>
      <PageHeader title="Catálogo" />

      <FormularioArticulo
        cargando={crear.isPending}
        error={codigoRepetido ? null : (crear.error?.message ?? null)}
        errorCodigo={codigoRepetido}
        ultimoCodigo={crear.data?.articulo.codigo ?? null}
        advertencias={crear.data?.advertencias ?? []}
        rubros={rubros}
        marcas={marcas}
        listas={listas}
        // Después del alta el catálogo salta a buscar el artículo recién creado. Es el cierre del
        // circuito: sin esto queda en la página que estaba mirando, donde el nuevo casi nunca cae.
        // `mutateAsync` y no `mutate` porque el formulario se limpia recién cuando el alta salió.
        onCrear={(v) =>
          crear.mutateAsync(v).then((r) => {
            setSearch({ q: r.articulo.codigo, page: 1 });
            return r;
          })
        }
      />

      <div className="flex flex-col gap-3 sm:flex-row sm:items-center">
        <SearchInput
          value={q}
          onChange={(e) => setSearch({ q: e.target.value, page: 1 })}
          placeholder="Buscar por código, detalle, marca… (probá 'filtro para el gol')"
          aria-label="Buscar en el catálogo"
          containerClassName="flex-1"
        />
        <div className="flex gap-2">
          <NativeSelect
            value={rubro}
            onChange={(e) => setSearch({ rubro: e.target.value, page: 1 })}
            aria-label="Filtrar por rubro"
            disabled={rubros.length === 0}
          >
            <option value="">Todos los rubros</option>
            {rubros.map((r) => (
              <option key={r} value={r}>
                {r}
              </option>
            ))}
          </NativeSelect>
          <NativeSelect
            value={marca}
            onChange={(e) => setSearch({ marca: e.target.value, page: 1 })}
            aria-label="Filtrar por marca"
            disabled={marcas.length === 0}
          >
            <option value="">Todas las marcas</option>
            {marcas.map((m) => (
              <option key={m} value={m}>
                {m}
              </option>
            ))}
          </NativeSelect>
        </div>
      </div>

      <PageBody>
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
            <ArticuloTable articulos={visibles} containerClassName="sm:min-h-0 sm:flex-1" />
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
      </PageBody>
    </PageLayout>
  );
}
