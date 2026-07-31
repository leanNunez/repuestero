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

import type { ArticuloItem } from "./schema";

export function ArticuloTable({ articulos }: { articulos: ArticuloItem[] }) {
  return (
    <Table>
      <TableHeader>
        <TableRow>
          <TableHead>Código</TableHead>
          <TableHead>Detalle</TableHead>
          <TableHead>Marca</TableHead>
          <TableHead>Rubro</TableHead>
          <TableHead className="text-right">IVA</TableHead>
          <TableHead className="text-right">Costo</TableHead>
        </TableRow>
      </TableHeader>
      <TableBody>
        {articulos.map((a) => (
          <TableRow key={a.id}>
            <TableCell>
              <Link
                to="/catalogo/$codigo"
                params={{ codigo: a.codigo }}
                className="font-medium text-primary hover:underline"
              >
                {a.codigo}
              </Link>
            </TableCell>
            <TableCell>{a.detalle}</TableCell>
            <TableCell>
              {a.marca ? <Badge>{a.marca}</Badge> : <span className="text-muted-foreground">—</span>}
            </TableCell>
            <TableCell className="text-muted-foreground">{a.rubro ?? "—"}</TableCell>
            <TableCell className="text-right tabular-nums text-muted-foreground">
              {formatNumber(a.alicuota_iva)}%
            </TableCell>
            <TableCell className="text-right font-medium">
              <Money value={a.costo} />
            </TableCell>
          </TableRow>
        ))}
      </TableBody>
    </Table>
  );
}
