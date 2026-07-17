import { Link } from "@tanstack/react-router";

import { formatNumber } from "@/shared/lib/format";
import { Badge } from "@/shared/ui/badge";

import type { ReposicionItem } from "../schema";

export function ReposicionTable({ items }: { items: ReposicionItem[] }) {
  return (
    <div className="overflow-x-auto">
      <table className="w-full text-left text-sm">
        <thead className="sticky top-0 z-10 border-b border-border bg-card text-xs text-muted-foreground">
          <tr>
            <th className="px-4 py-2.5 font-medium">Código</th>
            <th className="px-4 py-2.5 font-medium">Detalle</th>
            <th className="px-4 py-2.5 text-right font-medium">Stock</th>
            <th className="px-4 py-2.5 text-right font-medium">Punto pedido</th>
            <th className="px-4 py-2.5 text-right font-medium">Faltante</th>
          </tr>
        </thead>
        <tbody>
          {items.map((r) => (
            <tr key={r.codigo} className="border-b border-border last:border-0 hover:bg-muted/50">
              <td className="px-4 py-2.5">
                <Link
                  to="/catalogo/$codigo"
                  params={{ codigo: r.codigo }}
                  className="font-medium text-primary hover:underline"
                >
                  {r.codigo}
                </Link>
              </td>
              <td className="px-4 py-2.5">{r.detalle}</td>
              <td className="px-4 py-2.5 text-right tabular-nums">{formatNumber(r.stock)}</td>
              <td className="px-4 py-2.5 text-right tabular-nums text-muted-foreground">
                {formatNumber(r.punto_pedido)}
              </td>
              <td className="px-4 py-2.5 text-right">
                <Badge variant="warning">{formatNumber(r.faltante)}</Badge>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
