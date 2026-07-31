import { Link } from "@tanstack/react-router";

import { formatNumber } from "@/shared/lib/format";
import { Badge } from "@/shared/ui/badge";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/shared/ui/table";

import type { ReposicionItem } from "../schema";

export function ReposicionTable({ items }: { items: ReposicionItem[] }) {
  return (
    // Va dentro de un Card, que ya pone marco y fondo: el contenedor va desnudo.
    <Table containerClassName="rounded-none border-0 bg-transparent">
      <TableHeader>
        <TableRow>
          <TableHead>Código</TableHead>
          <TableHead>Detalle</TableHead>
          <TableHead className="text-right">Stock</TableHead>
          <TableHead className="text-right">Punto pedido</TableHead>
          <TableHead className="text-right">Faltante</TableHead>
        </TableRow>
      </TableHeader>
      <TableBody>
        {items.map((r) => (
          <TableRow key={r.codigo}>
            <TableCell>
              <Link
                to="/catalogo/$codigo"
                params={{ codigo: r.codigo }}
                className="font-medium text-primary hover:underline"
              >
                {r.codigo}
              </Link>
            </TableCell>
            <TableCell>{r.detalle}</TableCell>
            <TableCell className="text-right font-mono tabular-nums">
              {formatNumber(r.stock)}
            </TableCell>
            <TableCell className="text-right font-mono tabular-nums text-muted-foreground">
              {formatNumber(r.punto_pedido)}
            </TableCell>
            <TableCell className="text-right">
              <Badge variant="warning">{formatNumber(r.faltante)}</Badge>
            </TableCell>
          </TableRow>
        ))}
      </TableBody>
    </Table>
  );
}
