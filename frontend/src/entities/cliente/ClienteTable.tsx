import { formatMoney } from "@/shared/lib/format";
import { Badge } from "@/shared/ui/badge";

import type { Cliente } from "./schema";

/** "RESPONSABLE_INSCRIPTO" → "Responsable inscripto". */
function condLegible(cond: string): string {
  const t = cond.replace(/_/g, " ").toLowerCase();
  return t.charAt(0).toUpperCase() + t.slice(1);
}

export function ClienteTable({ clientes }: { clientes: Cliente[] }) {
  return (
    <div className="overflow-x-auto rounded-lg border border-border bg-card">
      <table className="w-full text-left text-sm">
        <thead className="sticky top-0 z-10 border-b border-border bg-card text-xs text-muted-foreground">
          <tr>
            <th className="px-4 py-2.5 font-medium">Código</th>
            <th className="px-4 py-2.5 font-medium">Denominación</th>
            <th className="px-4 py-2.5 font-medium">CUIT</th>
            <th className="px-4 py-2.5 font-medium">Condición</th>
            <th className="px-4 py-2.5 font-medium">Teléfono</th>
            <th className="px-4 py-2.5 text-right font-medium">Límite cta. cte.</th>
          </tr>
        </thead>
        <tbody>
          {clientes.map((c) => (
            <tr key={c.id} className="border-b border-border last:border-0 hover:bg-muted/50">
              <td className="px-4 py-2.5 font-medium">{c.codigo}</td>
              <td className="px-4 py-2.5">{c.denominacion}</td>
              <td className="px-4 py-2.5 tabular-nums text-muted-foreground">{c.cuit ?? "—"}</td>
              <td className="px-4 py-2.5">
                <Badge>{condLegible(c.cond_fiscal)}</Badge>
              </td>
              <td className="px-4 py-2.5 text-muted-foreground">{c.telefono ?? "—"}</td>
              <td className="px-4 py-2.5 text-right tabular-nums">
                {c.limite_cta_cte > 0 ? formatMoney(c.limite_cta_cte) : "—"}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
