import type { MovimientoCaja } from "@/entities/caja/schema";
import { fechaCorta } from "@/shared/lib/format";
import { Badge } from "@/shared/ui/badge";
import { Money } from "@/shared/ui/money";
import { TableSkeleton } from "@/shared/ui/query-state";
import { EmptyState, ErrorState } from "@/shared/ui/states";
import {
  Table,
  TableBody,
  TableCaption,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/shared/ui/table";

import { etiquetaConcepto, etiquetaForma } from "../model/estado";

interface Props {
  movimientos: MovimientoCaja[] | undefined;
  isLoading: boolean;
  isError: boolean;
  onRetry: () => void;
  /** Para que la página de altura fija le dé el alto sobrante y scrollee solo el cuerpo. */
  containerClassName?: string;
}

/** De dónde salió el movimiento: "Recibo #12", "Cheque #3", o "A mano".
 *
 * La distinción importa y no es cosmética: un movimiento con referencia lo emitió un documento y no
 * se toca a mano; uno sin referencia lo cargó una persona. Es el invariante del módulo hecho
 * visible. */
function origen(m: MovimientoCaja): string {
  if (!m.ref_tipo || m.ref_id === null) return "A mano";

  const nombre = m.ref_tipo.replace(/_/g, " ");
  return `${nombre.charAt(0).toUpperCase()}${nombre.slice(1)} #${m.ref_id}`;
}

export function MovimientosTable({
  movimientos,
  isLoading,
  isError,
  onRetry,
  containerClassName,
}: Props) {
  if (isLoading) return <TableSkeleton rows={8} className="h-10 w-full" />;
  if (isError) return <ErrorState onRetry={onRetry} />;
  if (!movimientos || movimientos.length === 0) {
    return (
      <EmptyState
        title="La caja no tiene movimientos"
        hint="Las cobranzas y los pagos entran acá automáticamente. Los gastos se cargan a mano."
      />
    );
  }

  return (
    <Table containerClassName={containerClassName}>
      <TableCaption className="sr-only">
        Movimientos de caja, del más reciente al más antiguo
      </TableCaption>
      <TableHeader>
        <TableRow>
          <TableHead scope="col">Fecha</TableHead>
          <TableHead scope="col">Concepto</TableHead>
          <TableHead scope="col">Origen</TableHead>
          {/* Sin esta columna, la de Saldo es ilegible: el acumulado se calcula POR FORMA, así
              que en el listado sin filtrar los números saltan entre particiones distintas y
              parecen incoherentes. La forma es la que explica el salto. */}
          <TableHead scope="col">Forma</TableHead>
          <TableHead scope="col" className="text-right">
            Entra
          </TableHead>
          <TableHead scope="col" className="text-right">
            Sale
          </TableHead>
          <TableHead scope="col" className="text-right">
            Saldo
            <span className="block text-[0.7rem] font-normal normal-case">de esa forma</span>
          </TableHead>
        </TableRow>
      </TableHeader>
      <TableBody>
        {movimientos.map((m) => (
          <TableRow key={m.id}>
            {/* Cuándo se MOVIÓ la plata arriba y, solo si difiere, cuándo se CARGÓ abajo. Sin esa
                segunda fecha el retroactivo sería una forma prolija de reescribir el pasado;
                mostrarla siempre sería ruido en la enorme mayoría de las filas. */}
            <TableCell className="whitespace-nowrap align-top tabular-nums">
              {fechaCorta(m.fecha)}
              {m.creado_en.slice(0, 10) !== m.fecha.slice(0, 10) && (
                <span className="mt-0.5 block text-xs font-normal text-muted-foreground">
                  cargado el {fechaCorta(m.creado_en)}
                </span>
              )}
            </TableCell>
            <TableCell className="align-top">
              {etiquetaConcepto(m.concepto)}
              {m.detalle && (
                <span className="mt-0.5 block max-w-xs text-xs text-muted-foreground">
                  {m.detalle}
                </span>
              )}
            </TableCell>
            <TableCell className="align-top text-muted-foreground">
              {m.ref_tipo ? origen(m) : <Badge>A mano</Badge>}
            </TableCell>
            <TableCell className="whitespace-nowrap align-top text-muted-foreground">
              {etiquetaForma(m.forma)}
            </TableCell>
            <TableCell className="text-right align-top">
              <Money value={Number(m.ingreso) > 0 ? m.ingreso : null} centavos />
            </TableCell>
            <TableCell className="text-right align-top">
              <Money value={Number(m.egreso) > 0 ? m.egreso : null} centavos />
            </TableCell>
            {/* El acumulado viene calculado del backend sobre TODO el libro, particionado por
                forma. No se recalcula acá: esta tabla tiene una página y no conoce lo anterior. */}
            <TableCell className="text-right align-top font-medium">
              <Money value={m.saldo_acumulado} centavos />
            </TableCell>
          </TableRow>
        ))}
      </TableBody>
    </Table>
  );
}
