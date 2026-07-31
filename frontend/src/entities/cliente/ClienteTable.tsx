import { iniciales } from "@/shared/lib/format";
import { Badge } from "@/shared/ui/badge";
import { Money } from "@/shared/ui/money";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/shared/ui/table";

import type { Cliente } from "./schema";

/** "RESPONSABLE_INSCRIPTO" → "Responsable inscripto". */
function condLegible(cond: string): string {
  const t = cond.replace(/_/g, " ").toLowerCase();
  return t.charAt(0).toUpperCase() + t.slice(1);
}

export function ClienteTable({
  clientes,
  containerClassName,
}: {
  clientes: Cliente[];
  /** Para que la página de altura fija le dé el alto sobrante y scrollee solo el cuerpo. */
  containerClassName?: string;
}) {
  return (
    <Table containerClassName={containerClassName}>
      <TableHeader>
        <TableRow>
          <TableHead>Código</TableHead>
          <TableHead>Denominación</TableHead>
          <TableHead>CUIT</TableHead>
          <TableHead>Condición</TableHead>
          <TableHead>Teléfono</TableHead>
          <TableHead className="text-right">Límite cta. cte.</TableHead>
        </TableRow>
      </TableHeader>
      <TableBody>
        {clientes.map((c) => (
          <TableRow key={c.id}>
            <TableCell className="font-medium">{c.codigo}</TableCell>
            <TableCell>
              <div className="flex items-center gap-2.5">
                <span className="flex h-7 w-7 shrink-0 items-center justify-center rounded-full bg-primary/10 text-[11px] font-semibold text-primary">
                  {iniciales(c.denominacion)}
                </span>
                <span>{c.denominacion}</span>
              </div>
            </TableCell>
            <TableCell className="tabular-nums text-muted-foreground">{c.cuit ?? "—"}</TableCell>
            <TableCell>
              <Badge>{condLegible(c.cond_fiscal)}</Badge>
            </TableCell>
            <TableCell className="text-muted-foreground">{c.telefono ?? "—"}</TableCell>
            <TableCell className="text-right">
              <Money value={c.limite_cta_cte > 0 ? c.limite_cta_cte : null} />
            </TableCell>
          </TableRow>
        ))}
      </TableBody>
    </Table>
  );
}
