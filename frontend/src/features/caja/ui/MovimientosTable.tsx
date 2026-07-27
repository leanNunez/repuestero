import type { MovimientoCaja } from "@/entities/caja/schema";
import { pesos } from "@/entities/remito/formato";
import { fechaCorta } from "@/shared/lib/format";
import { Badge } from "@/shared/ui/badge";
import { Skeleton } from "@/shared/ui/skeleton";
import { EmptyState, ErrorState } from "@/shared/ui/states";

import { etiquetaConcepto } from "../model/estado";

interface Props {
  movimientos: MovimientoCaja[] | undefined;
  isLoading: boolean;
  isError: boolean;
  onRetry: () => void;
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

export function MovimientosTable({ movimientos, isLoading, isError, onRetry }: Props) {
  if (isLoading) {
    return (
      <div className="space-y-2">
        {Array.from({ length: 8 }).map((_, i) => (
          <Skeleton key={i} className="h-10 w-full" />
        ))}
      </div>
    );
  }
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
    <div className="overflow-x-auto rounded-lg border border-border bg-card">
      <table className="w-full text-left text-sm">
        <caption className="sr-only">
          Movimientos de caja, del más reciente al más antiguo
        </caption>
        <thead className="border-b border-border text-xs text-muted-foreground">
          <tr>
            <th scope="col" className="px-4 py-2.5 font-medium">
              Fecha
            </th>
            <th scope="col" className="px-4 py-2.5 font-medium">
              Concepto
            </th>
            <th scope="col" className="px-4 py-2.5 font-medium">
              Origen
            </th>
            <th scope="col" className="px-4 py-2.5 text-right font-medium">
              Entra
            </th>
            <th scope="col" className="px-4 py-2.5 text-right font-medium">
              Sale
            </th>
            <th scope="col" className="px-4 py-2.5 text-right font-medium">
              Saldo
            </th>
          </tr>
        </thead>
        <tbody>
          {movimientos.map((m) => (
            <tr key={m.id} className="border-b border-border last:border-0 hover:bg-muted/50">
              {/* Cuándo se MOVIÓ la plata arriba y, solo si difiere, cuándo se CARGÓ abajo. Sin esa
                  segunda fecha el retroactivo sería una forma prolija de reescribir el pasado;
                  mostrarla siempre sería ruido en la enorme mayoría de las filas. */}
              <td className="whitespace-nowrap px-4 py-2.5 align-top tabular-nums">
                {fechaCorta(m.fecha)}
                {m.creado_en.slice(0, 10) !== m.fecha.slice(0, 10) && (
                  <span className="mt-0.5 block text-xs font-normal text-muted-foreground">
                    cargado el {fechaCorta(m.creado_en)}
                  </span>
                )}
              </td>
              <td className="px-4 py-2.5 align-top">
                {etiquetaConcepto(m.concepto)}
                {m.detalle && (
                  <span className="mt-0.5 block max-w-xs text-xs text-muted-foreground">
                    {m.detalle}
                  </span>
                )}
              </td>
              <td className="px-4 py-2.5 align-top text-muted-foreground">
                {m.ref_tipo ? origen(m) : <Badge>A mano</Badge>}
              </td>
              <td className="px-4 py-2.5 text-right align-top tabular-nums">
                {Number(m.ingreso) > 0 ? pesos(m.ingreso) : "—"}
              </td>
              <td className="px-4 py-2.5 text-right align-top tabular-nums">
                {Number(m.egreso) > 0 ? pesos(m.egreso) : "—"}
              </td>
              {/* El acumulado viene calculado del backend sobre TODO el libro, particionado por
                  forma. No se recalcula acá: esta tabla tiene una página y no conoce lo anterior. */}
              <td className="px-4 py-2.5 text-right align-top font-medium tabular-nums">
                {pesos(m.saldo_acumulado)}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
