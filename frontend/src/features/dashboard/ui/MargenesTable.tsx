import { Link } from "@tanstack/react-router";

import { formatMoney, formatNumber } from "@/shared/lib/format";
import { Badge } from "@/shared/ui/badge";

import type { MargenItem } from "../schema";

export function MargenesTable({ items }: { items: MargenItem[] }) {
  return (
    <div className="overflow-x-auto rounded-lg border border-border bg-card">
      <table className="w-full text-left text-sm">
        <thead className="border-b border-border text-xs text-muted-foreground">
          <tr>
            <th className="px-4 py-2.5 font-medium">Código</th>
            <th className="px-4 py-2.5 font-medium">Detalle</th>
            <th className="px-4 py-2.5 text-right font-medium">Costo</th>
            <th className="px-4 py-2.5 text-right font-medium">Precio</th>
            <th className="px-4 py-2.5 text-right font-medium">Margen</th>
          </tr>
        </thead>
        <tbody>
          {items.map((m) => (
            <tr key={m.codigo} className="border-b border-border last:border-0 hover:bg-muted/50">
              <td className="px-4 py-2.5">
                <Link
                  to="/catalogo/$codigo"
                  params={{ codigo: m.codigo }}
                  className="font-medium text-primary hover:underline"
                >
                  {m.codigo}
                </Link>
              </td>
              <td className="px-4 py-2.5">{m.detalle}</td>
              <td className="px-4 py-2.5 text-right tabular-nums text-muted-foreground">
                {formatMoney(m.costo)}
              </td>
              <td className="px-4 py-2.5 text-right tabular-nums">{formatMoney(m.precio)}</td>
              <td className="px-4 py-2.5 text-right">
                <Badge variant="danger">{formatNumber(m.margen)}%</Badge>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
