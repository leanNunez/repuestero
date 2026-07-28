import { iniciales } from "@/shared/lib/format";

import type { Proveedor } from "./schema";

/** Sin columna de límite de cuenta corriente, a diferencia de la tabla de clientes: a un proveedor
 *  no se le fija un límite de crédito — la deuda va para el otro lado. */
export function ProveedorTable({ proveedores }: { proveedores: Proveedor[] }) {
  return (
    <div className="overflow-x-auto rounded-lg border border-border bg-card">
      <table className="w-full text-left text-sm">
        <thead className="sticky top-0 z-10 border-b border-border bg-card text-xs text-muted-foreground">
          <tr>
            <th className="px-4 py-2.5 font-medium">Código</th>
            <th className="px-4 py-2.5 font-medium">Razón social</th>
            <th className="px-4 py-2.5 font-medium">CUIT</th>
            <th className="px-4 py-2.5 font-medium">Teléfono</th>
            <th className="px-4 py-2.5 font-medium">Email</th>
          </tr>
        </thead>
        <tbody>
          {proveedores.map((p) => (
            <tr key={p.id} className="border-b border-border last:border-0 hover:bg-muted/50">
              <td className="px-4 py-2.5 font-medium">{p.codigo}</td>
              <td className="px-4 py-2.5">
                <div className="flex items-center gap-2.5">
                  <span className="flex h-7 w-7 shrink-0 items-center justify-center rounded-full bg-primary/10 text-[11px] font-semibold text-primary">
                    {iniciales(p.razon_social)}
                  </span>
                  <span>{p.razon_social}</span>
                </div>
              </td>
              <td className="px-4 py-2.5 tabular-nums text-muted-foreground">{p.cuit ?? "—"}</td>
              <td className="px-4 py-2.5 text-muted-foreground">{p.telefono ?? "—"}</td>
              <td className="px-4 py-2.5 text-muted-foreground">{p.email ?? "—"}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
