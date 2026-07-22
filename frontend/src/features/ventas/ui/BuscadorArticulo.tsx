import { Plus } from "lucide-react";
import { useState } from "react";

import type { ArticuloItem } from "@/entities/articulo/schema";
import { useCatalogo } from "@/features/catalogo-search/model/hooks";
import { Card } from "@/shared/ui/card";

const inputClass =
  "h-9 w-full rounded-md border border-input bg-background px-3 text-sm focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring";

/** Busca un artículo (búsqueda híbrida del catálogo) y lo agrega como renglón al hacer click.
 * Al agregar, limpia el texto para encadenar cargas rápidas en el mostrador. */
export function BuscadorArticulo({ onAgregar }: { onAgregar: (a: ArticuloItem) => void }) {
  const [q, setQ] = useState("");
  const { data, isFetching } = useCatalogo(q, 1, "", "");
  const texto = q.trim();
  const items = texto ? (data?.items ?? []) : [];

  return (
    <div className="space-y-2">
      <input
        value={q}
        onChange={(e) => setQ(e.target.value)}
        placeholder="Buscá un artículo por nombre o código…"
        className={inputClass}
        aria-label="Buscar artículo"
      />
      {texto && (
        <Card className="max-h-64 divide-y overflow-auto p-0">
          {isFetching && items.length === 0 && (
            <p className="p-3 text-sm text-muted-foreground">Buscando…</p>
          )}
          {!isFetching && items.length === 0 && (
            <p className="p-3 text-sm text-muted-foreground">Sin resultados para «{texto}».</p>
          )}
          {items.map((a) => (
            <button
              key={a.codigo}
              onClick={() => {
                onAgregar(a);
                setQ("");
              }}
              className="flex w-full items-center justify-between gap-3 p-3 text-left text-sm hover:bg-muted"
            >
              <span className="min-w-0">
                <span className="font-medium">{a.detalle}</span>
                <span className="text-muted-foreground"> · {a.codigo}</span>
              </span>
              <Plus className="h-4 w-4 shrink-0 text-muted-foreground" />
            </button>
          ))}
        </Card>
      )}
    </div>
  );
}
