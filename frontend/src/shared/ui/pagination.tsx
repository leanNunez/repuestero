import { Button } from "@/shared/ui/button";

type PaginationProps = {
  page: number;
  pageSize: number;
  total: number;
  onPageChange: (page: number) => void;
};

/** Ventana de páginas alrededor de la actual, con elipsis. Ej.: 1 … 4 [5] 6 … 20 */
function ventana(page: number, totalPages: number): (number | "…")[] {
  const cercanas = new Set([1, totalPages, page, page - 1, page + 1]);
  const paginas = [...cercanas].filter((p) => p >= 1 && p <= totalPages).sort((a, b) => a - b);
  const resultado: (number | "…")[] = [];
  let previa = 0;
  for (const p of paginas) {
    if (previa && p - previa > 1) resultado.push("…");
    resultado.push(p);
    previa = p;
  }
  return resultado;
}

/** Paginación clásica: Anterior · números (con elipsis) · Siguiente. No renderiza con 1 página. */
export function Pagination({ page, pageSize, total, onPageChange }: PaginationProps) {
  const totalPages = Math.ceil(total / pageSize);
  if (totalPages <= 1) return null;

  return (
    <nav aria-label="Paginación" className="flex flex-wrap items-center justify-center gap-1">
      <Button
        variant="outline"
        size="sm"
        disabled={page <= 1}
        onClick={() => onPageChange(page - 1)}
      >
        Anterior
      </Button>

      {ventana(page, totalPages).map((p, i) =>
        p === "…" ? (
          <span key={`gap-${i}`} className="px-2 text-sm text-muted-foreground" aria-hidden>
            …
          </span>
        ) : (
          <Button
            key={p}
            variant={p === page ? "default" : "ghost"}
            size="sm"
            aria-current={p === page ? "page" : undefined}
            onClick={() => onPageChange(p)}
          >
            {p}
          </Button>
        ),
      )}

      <Button
        variant="outline"
        size="sm"
        disabled={page >= totalPages}
        onClick={() => onPageChange(page + 1)}
      >
        Siguiente
      </Button>
    </nav>
  );
}
