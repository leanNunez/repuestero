import { Link } from "@tanstack/react-router";

import { formatNumber } from "@/shared/lib/format";
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

import type { MargenItem } from "../schema";

export function MargenesTable({ items }: { items: MargenItem[] }) {
  return (
    // Va dentro de un Card, que ya pone marco y fondo: el contenedor va desnudo.
    <Table containerClassName="rounded-none border-0 bg-transparent">
      <TableHeader>
        <TableRow>
          <TableHead>Código</TableHead>
          <TableHead>Detalle</TableHead>
          <TableHead className="text-right">Costo</TableHead>
          <TableHead className="text-right">Precio</TableHead>
          <TableHead className="text-right">Margen</TableHead>
        </TableRow>
      </TableHeader>
      <TableBody>
        {items.map((m) => (
          <TableRow key={m.codigo}>
            <TableCell>
              <Link
                to="/catalogo/$codigo"
                params={{ codigo: m.codigo }}
                className="font-medium text-primary hover:underline"
              >
                {m.codigo}
              </Link>
            </TableCell>
            <TableCell>{m.detalle}</TableCell>
            <TableCell className="text-right">
              <Money value={m.costo} className="text-muted-foreground" />
            </TableCell>
            <TableCell className="text-right">
              <Money value={m.precio} />
            </TableCell>
            <TableCell className="text-right">
              <Badge variant="danger">{formatNumber(m.margen)}%</Badge>
            </TableCell>
          </TableRow>
        ))}
      </TableBody>
    </Table>
  );
}
