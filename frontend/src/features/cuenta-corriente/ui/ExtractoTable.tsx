import type { Movimiento } from "@/entities/cuenta-corriente/schema";
import { pesos } from "@/entities/remito/formato";
import { fechaCorta } from "@/shared/lib/format";
import { Badge } from "@/shared/ui/badge";
import { Button } from "@/shared/ui/button";
import { Skeleton } from "@/shared/ui/skeleton";
import { EmptyState, ErrorState } from "@/shared/ui/states";

import { etiquetaTipo } from "../model/estado";

interface Props {
  movimientos: Movimiento[] | undefined;
  isLoading: boolean;
  isError: boolean;
  onRetry: () => void;
  /** Abrir el formulario de ajuste en modo reversa para esta fila. */
  onRevertir: (m: Movimiento) => void;
}

/** Referencia legible del movimiento: "Comprobante #123".
 *
 * Las cobranzas y los pagos llegan SIN referencia —el service no las guarda todavía—, así que
 * esta columna va a estar vacía justo en las filas que el operador acaba de crear. */
function referencia(m: Movimiento): string {
  if (!m.ref_tipo || m.ref_id === null) return "—";

  const nombre = m.ref_tipo.replace(/_/g, " ");
  return `${nombre.charAt(0).toUpperCase()}${nombre.slice(1)} #${m.ref_id}`;
}

export function ExtractoTable({ movimientos, isLoading, isError, onRetry, onRevertir }: Props) {
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
        title="Esta cuenta no tiene movimientos"
        hint="Las ventas y compras a cuenta corriente aparecen acá automáticamente."
      />
    );
  }

  return (
    <div className="overflow-x-auto rounded-lg border border-border bg-card">
      <table className="w-full text-left text-sm">
        <caption className="sr-only">
          Movimientos de la cuenta corriente, del más reciente al más antiguo
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
              Referencia
            </th>
            <th scope="col" className="px-4 py-2.5 text-right font-medium">
              Debe
            </th>
            <th scope="col" className="px-4 py-2.5 text-right font-medium">
              Haber
            </th>
            <th scope="col" className="px-4 py-2.5 text-right font-medium">
              Saldo
            </th>
            <th scope="col" className="px-4 py-2.5 font-medium">
              <span className="sr-only">Acciones</span>
            </th>
          </tr>
        </thead>
        <tbody>
          {movimientos.map((m) => (
            <tr key={m.id} className="border-b border-border last:border-0 hover:bg-muted/50">
              <td className="whitespace-nowrap px-4 py-2.5 align-top tabular-nums">
                {fechaCorta(m.fecha)}
              </td>
              <td className="px-4 py-2.5 align-top">
                <span className={m.anulado ? "text-muted-foreground line-through" : undefined}>
                  {etiquetaTipo(m.tipo)}
                </span>
                {m.motivo && (
                  <span className="mt-0.5 block max-w-xs text-xs text-muted-foreground">
                    {m.motivo}
                  </span>
                )}
              </td>
              <td className="px-4 py-2.5 align-top text-muted-foreground">{referencia(m)}</td>
              <td className="px-4 py-2.5 text-right align-top tabular-nums">
                {Number(m.debe) > 0 ? pesos(m.debe) : "—"}
              </td>
              <td className="px-4 py-2.5 text-right align-top tabular-nums">
                {Number(m.haber) > 0 ? pesos(m.haber) : "—"}
              </td>
              {/* El acumulado viene calculado del backend sobre TODO el ledger. No se recalcula
                  acá: esta tabla solo tiene una página y no conoce lo anterior. */}
              <td className="px-4 py-2.5 text-right align-top font-medium tabular-nums">
                {pesos(m.saldo_acumulado)}
              </td>
              {/* Un movimiento anulado muestra el estado en vez del botón. Del resto, `reversible`
                  ya viene resuelto por el backend: los tipos que espejan un comprobante llegan en
                  false porque se corrigen por su propio flujo, no desde el ledger. */}
              <td className="whitespace-nowrap px-4 py-2.5 align-top">
                {m.anulado && <Badge variant="warning">Anulado</Badge>}
                {m.reversible && (
                  <Button
                    variant="ghost"
                    size="sm"
                    onClick={() => onRevertir(m)}
                    aria-label={`Revertir ${etiquetaTipo(m.tipo).toLowerCase()} del ${fechaCorta(m.fecha)}`}
                  >
                    Revertir
                  </Button>
                )}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
