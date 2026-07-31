import { iniciales } from "@/shared/lib/format";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/shared/ui/table";

import type { Proveedor } from "./schema";

/** Sin columna de límite de cuenta corriente, a diferencia de la tabla de clientes: a un proveedor
 *  no se le fija un límite de crédito — la deuda va para el otro lado. */
export function ProveedorTable({ proveedores }: { proveedores: Proveedor[] }) {
  return (
    <Table>
      <TableHeader>
        <TableRow>
          <TableHead>Código</TableHead>
          <TableHead>Razón social</TableHead>
          <TableHead>CUIT</TableHead>
          <TableHead>Teléfono</TableHead>
          <TableHead>Email</TableHead>
        </TableRow>
      </TableHeader>
      <TableBody>
        {proveedores.map((p) => (
          <TableRow key={p.id}>
            <TableCell className="font-medium">{p.codigo}</TableCell>
            <TableCell>
              <div className="flex items-center gap-2.5">
                <span className="flex h-7 w-7 shrink-0 items-center justify-center rounded-full bg-primary/10 text-[11px] font-semibold text-primary">
                  {iniciales(p.razon_social)}
                </span>
                <span>{p.razon_social}</span>
              </div>
            </TableCell>
            <TableCell className="tabular-nums text-muted-foreground">{p.cuit ?? "—"}</TableCell>
            <TableCell className="text-muted-foreground">{p.telefono ?? "—"}</TableCell>
            <TableCell className="text-muted-foreground">{p.email ?? "—"}</TableCell>
          </TableRow>
        ))}
      </TableBody>
    </Table>
  );
}
