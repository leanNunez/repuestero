import type { ReactNode } from "react";

import { Skeleton } from "./skeleton";
import { EmptyState, ErrorState } from "./states";

/* Estructural a propósito: cualquier resultado de useQuery calza sin acoplar
   este primitivo a la versión de TanStack Query. */
interface QueryLike<T> {
  isLoading: boolean;
  isError: boolean;
  data: T | undefined;
  refetch: () => unknown;
}

interface Props<T> {
  query: QueryLike<T>;
  /** Skeleton a mostrar durante la carga. Por defecto, filas de tabla. */
  skeleton?: ReactNode;
  /** Si está, se muestra EmptyState cuando `isEmpty(data)` (o `data.length === 0` en arrays). */
  empty?: { title: string; hint?: ReactNode };
  isEmpty?: (data: T) => boolean;
  children: (data: T) => ReactNode;
}

/** Encapsula el ternario loading → error → vacío → datos que cada página repetía a mano.
 *  El orden de los estados es la política de la casa: skeleton (nunca spinner para grillas),
 *  error con reintento, vacío con texto útil, y recién entonces los datos. */
export function QueryState<T>({ query, skeleton, empty, isEmpty, children }: Props<T>) {
  if (query.isLoading) return <>{skeleton ?? <TableSkeleton />}</>;
  if (query.isError) return <ErrorState onRetry={() => void query.refetch()} />;
  if (query.data === undefined) return null;

  const vacio = isEmpty
    ? isEmpty(query.data)
    : Array.isArray(query.data) && query.data.length === 0;
  if (vacio && empty) return <EmptyState title={empty.title} hint={empty.hint} />;

  return <>{children(query.data)}</>;
}

/** Las filas fantasma que cada listado armaba con su propio Array.from. */
export function TableSkeleton({ rows = 6, className }: { rows?: number; className?: string }) {
  return (
    <div className="space-y-2">
      {Array.from({ length: rows }).map((_, i) => (
        <Skeleton key={i} className={className ?? "h-11 w-full"} />
      ))}
    </div>
  );
}
