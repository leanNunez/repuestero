import { Link } from "@tanstack/react-router";

import { formatMoney } from "@/shared/lib/format";
import { Badge } from "@/shared/ui/badge";

import type { ArticuloItem } from "./schema";

export function ArticuloTable({ articulos }: { articulos: ArticuloItem[] }) {
  return (
    <div className="overflow-x-auto rounded-lg border border-border bg-card">
      <table className="w-full text-left text-sm">
        <thead className="border-b border-border text-xs text-muted-foreground">
          <tr>
            <th className="px-4 py-2.5 font-medium">Código</th>
            <th className="px-4 py-2.5 font-medium">Detalle</th>
            <th className="px-4 py-2.5 font-medium">Marca</th>
            <th className="px-4 py-2.5 text-right font-medium">Costo</th>
          </tr>
        </thead>
        <tbody>
          {articulos.map((a) => (
            <tr key={a.id} className="border-b border-border last:border-0 hover:bg-muted/50">
              <td className="px-4 py-2.5">
                <Link
                  to="/catalogo/$codigo"
                  params={{ codigo: a.codigo }}
                  className="font-medium text-primary hover:underline"
                >
                  {a.codigo}
                </Link>
              </td>
              <td className="px-4 py-2.5">{a.detalle}</td>
              <td className="px-4 py-2.5">
                {a.marca ? <Badge>{a.marca}</Badge> : <span className="text-muted-foreground">—</span>}
              </td>
              <td className="px-4 py-2.5 text-right tabular-nums">{formatMoney(a.costo)}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
