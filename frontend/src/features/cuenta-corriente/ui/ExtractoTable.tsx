import type { Movimiento } from "@/entities/cuenta-corriente/schema";
import { fechaCorta } from "@/shared/lib/format";
import { Badge } from "@/shared/ui/badge";
import { Button } from "@/shared/ui/button";
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

import { etiquetaTipo } from "../model/estado";

interface Props {
  movimientos: Movimiento[] | undefined;
  isLoading: boolean;
  isError: boolean;
  onRetry: () => void;
  /** Abrir el formulario de ajuste en modo reversa para esta fila. */
  onRevertir: (m: Movimiento) => void;
  /** Anular el DOCUMENTO de esta fila (el recibo o la orden de pago), no el movimiento. */
  onAnular: (m: Movimiento) => void;
  /** Para que la página de altura fija le dé el alto sobrante y scrollee solo el cuerpo. */
  containerClassName?: string;
}

/** Referencia legible del movimiento: "Comprobante #123", "Recibo #47".
 *
 * Las cobranzas y los pagos SÍ traen referencia desde la migración 0010: apuntan al recibo o a la
 * orden de pago que emitieron. Las ANTERIORES a esa fecha se quedan con el guión para siempre, y
 * es a propósito — fabricarles un recibo retroactivo sería inventar un documento con un número
 * correlativo que nunca se imprimió.
 *
 * Ojo: el `#` es el ID INTERNO, no el número del documento que el cliente tiene en la mano
 * ("0001-00000012"). Se hereda de "Comprobante #", no se introduce acá. El arreglo correcto es un
 * `ref_etiqueta` calculado en el SQL del extracto, no un join desde el front. Anotado en
 * docs/pendientes.md. */
function referencia(m: Movimiento): string {
  if (!m.ref_tipo || m.ref_id === null) return "—";

  const nombre = m.ref_tipo.replace(/_/g, " ");
  return `${nombre.charAt(0).toUpperCase()}${nombre.slice(1)} #${m.ref_id}`;
}

export function ExtractoTable({
  movimientos,
  isLoading,
  isError,
  onRetry,
  onRevertir,
  onAnular,
  containerClassName,
}: Props) {
  if (isLoading) return <TableSkeleton rows={8} className="h-10 w-full" />;
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
    <Table containerClassName={containerClassName}>
      <TableCaption className="sr-only">
        Movimientos de la cuenta corriente, del más reciente al más antiguo
      </TableCaption>
      <TableHeader>
        <TableRow>
          <TableHead scope="col">Fecha</TableHead>
          <TableHead scope="col">Concepto</TableHead>
          <TableHead scope="col">Referencia</TableHead>
          <TableHead scope="col" className="text-right">
            Debe
          </TableHead>
          <TableHead scope="col" className="text-right">
            Haber
          </TableHead>
          <TableHead scope="col" className="text-right">
            Saldo
          </TableHead>
          <TableHead scope="col">
            <span className="sr-only">Acciones</span>
          </TableHead>
        </TableRow>
      </TableHeader>
      <TableBody>
        {movimientos.map((m) => (
          <TableRow key={m.id}>
            {/* Cuándo PASÓ arriba y, solo si difiere, cuándo se CARGÓ abajo. Sin esa segunda
                fecha el retroactivo sería una forma prolija de reescribir el pasado; mostrarla
                siempre sería ruido en todas las filas, que es la enorme mayoría. */}
            <TableCell className="whitespace-nowrap align-top tabular-nums">
              {fechaCorta(m.fecha)}
              {m.creado_en.slice(0, 10) !== m.fecha.slice(0, 10) && (
                <span className="mt-0.5 block text-xs font-normal text-muted-foreground">
                  cargado el {fechaCorta(m.creado_en)}
                </span>
              )}
            </TableCell>
            <TableCell className="align-top">
              <span className={m.anulado ? "text-muted-foreground line-through" : undefined}>
                {etiquetaTipo(m.tipo)}
              </span>
              {m.motivo && (
                <span className="mt-0.5 block max-w-xs text-xs text-muted-foreground">
                  {m.motivo}
                </span>
              )}
            </TableCell>
            <TableCell className="align-top text-muted-foreground">{referencia(m)}</TableCell>
            <TableCell className="text-right align-top">
              <Money value={Number(m.debe) > 0 ? m.debe : null} centavos />
            </TableCell>
            <TableCell className="text-right align-top">
              <Money value={Number(m.haber) > 0 ? m.haber : null} centavos />
            </TableCell>
            {/* El acumulado viene calculado del backend sobre TODO el ledger. No se recalcula
                acá: esta tabla solo tiene una página y no conoce lo anterior. */}
            <TableCell className="text-right align-top font-medium">
              <Money value={m.saldo_acumulado} centavos />
            </TableCell>
            {/* Un movimiento anulado muestra el estado en vez del botón. Del resto, `reversible` y
                `anulable` vienen YA resueltos por el backend, y son excluyentes por construcción:
                un ajuste se revierte desde el ledger, y una cobranza se anula desde su documento
                —porque el recibo movió además caja y cartera, y revertir solo el ledger dejaría
                esas dos cosas vivas—. El front no combina nada: dibuja el botón que le dicen. */}
            <TableCell className="whitespace-nowrap align-top">
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
              {m.anulable && (
                <Button
                  variant="ghost"
                  size="sm"
                  onClick={() => onAnular(m)}
                  aria-label={`Anular ${referencia(m).toLowerCase()} del ${fechaCorta(m.fecha)}`}
                >
                  Anular
                </Button>
              )}
            </TableCell>
          </TableRow>
        ))}
      </TableBody>
    </Table>
  );
}
