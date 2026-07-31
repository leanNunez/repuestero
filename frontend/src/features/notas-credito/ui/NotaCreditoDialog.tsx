import { AlertTriangle, Loader2, Undo2 } from "lucide-react";
import { useEffect, useReducer } from "react";

import { pesos } from "@/entities/remito/formato";
import type { VentaLeer } from "@/entities/venta/schema";
import {
  aRenglonesPayload,
  desdeAcreditables,
  ESTADO_INICIAL,
  puedeEmitir,
  reducer,
  totales,
} from "@/features/notas-credito/model/estado";
import {
  useEmitirNotaCredito,
  useRenglonesAcreditables,
} from "@/features/notas-credito/model/hooks";
import { Button } from "@/shared/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from "@/shared/ui/dialog";
import { Input } from "@/shared/ui/input";
import { Money } from "@/shared/ui/money";
import { TableSkeleton } from "@/shared/ui/query-state";
import { EmptyState, ErrorState } from "@/shared/ui/states";
import { SuccessPanel } from "@/shared/ui/success-panel";

function comprobanteLabel(tipo: string, ptoVenta: number, numero: number): string {
  return `${tipo} ${String(ptoVenta).padStart(4, "0")}-${String(numero).padStart(8, "0")}`;
}

interface Props {
  venta: VentaLeer | null;
  onClose: () => void;
}

/** Diálogo para emitir una nota de crédito sobre una venta.
 *
 * El foco, el Escape y el `aria-modal` los resuelve Radix; antes estaban a mano y sin trap real
 * —se podía tabular fuera del diálogo hacia la página de atrás—. El cuerpo se monta fresco por
 * cada apertura (keyed por `venta.id`): así reabrir la misma venta re-inicializa el estado desde
 * los acreditables, aunque React Query devuelva la data cacheada con la misma referencia. */
export function NotaCreditoDialog({ venta, onClose }: Props) {
  return (
    <Dialog
      open={venta !== null}
      onOpenChange={(abierto) => {
        if (!abierto) onClose();
      }}
    >
      {venta && <Contenido key={venta.id} venta={venta} onClose={onClose} />}
    </Dialog>
  );
}

/** Precarga cada renglón en su máximo acreditable (anulación total por defecto); el operador baja
 * las cantidades para una parcial. */
function Contenido({ venta, onClose }: { venta: VentaLeer; onClose: () => void }) {
  const [estado, dispatch] = useReducer(reducer, ESTADO_INICIAL);
  const acreditables = useRenglonesAcreditables(venta.id);
  const emitir = useEmitirNotaCredito();

  // Al llegar los renglones acreditables, arma el estado inicial.
  useEffect(() => {
    if (acreditables.data)
      dispatch({ type: "init", renglones: desdeAcreditables(acreditables.data) });
  }, [acreditables.data]);

  const label = comprobanteLabel(venta.tipo, venta.pto_venta, venta.numero);
  const tot = totales(estado.renglones);

  return (
    <DialogContent
      showCloseButton={false}
      className="flex max-h-[90vh] max-w-lg flex-col gap-0 overflow-hidden p-0"
    >
      <DialogHeader className="border-b border-border p-4">
        <DialogTitle className="text-base">Nota de crédito</DialogTitle>
        <DialogDescription className="text-xs">
          Sobre <span className="font-mono tabular-nums">{label}</span> · Total {pesos(venta.total)}
        </DialogDescription>
      </DialogHeader>

      <div className="min-h-0 flex-1 overflow-y-auto p-4">
        {emitir.data ? (
          <SuccessPanel className="py-6">
            <div>
              <h3 className="font-semibold">Nota de crédito emitida</h3>
              <p className="mt-1 text-sm text-muted-foreground">
                {comprobanteLabel(emitir.data.tipo, emitir.data.pto_venta, emitir.data.numero)} ·
                Total {pesos(emitir.data.total)}
              </p>
            </div>
            <Button variant="outline" onClick={onClose}>
              Listo
            </Button>
          </SuccessPanel>
        ) : acreditables.isLoading ? (
          <TableSkeleton rows={3} className="h-12 w-full" />
        ) : acreditables.isError ? (
          <ErrorState onRetry={() => void acreditables.refetch()} />
        ) : estado.renglones.length === 0 ? (
          <EmptyState
            title="No queda nada por acreditar"
            hint="Esta venta ya tiene notas de crédito por el total."
          />
        ) : (
          <div className="space-y-4">
            <div className="divide-y divide-border rounded-md border border-border">
              {estado.renglones.map((r, i) => (
                <div key={r.articulo_codigo} className="flex items-center justify-between gap-3 p-3">
                  <div className="min-w-0">
                    <p className="truncate text-sm font-medium">{r.descripcion}</p>
                    <p className="text-xs tabular-nums text-muted-foreground">
                      {r.articulo_codigo} · {pesos(r.precio_unitario)} c/u · hasta{" "}
                      {r.cantidad_acreditable}
                    </p>
                  </div>
                  <Input
                    type="text"
                    inputMode="decimal"
                    value={r.cantidad_acreditar}
                    onChange={(e) => dispatch({ type: "cantidad", i, valor: e.target.value })}
                    aria-label={`Cantidad a acreditar de ${r.descripcion}`}
                    className="w-24 tabular-nums"
                  />
                </div>
              ))}
            </div>

            <div className="flex flex-wrap items-end justify-between gap-3 border-t border-border pt-3">
              <div className="space-y-0.5 text-sm">
                <p className="text-muted-foreground">
                  Neto <Money value={tot.neto} centavos className="font-medium text-foreground" /> ·
                  IVA <Money value={tot.iva} centavos className="font-medium text-foreground" />
                </p>
                <p className="text-lg font-semibold">
                  Total <Money value={tot.total} centavos />
                </p>
              </div>

              <Button
                onClick={() =>
                  emitir.mutate({ comprobante_id: venta.id, renglones: aRenglonesPayload(estado) })
                }
                disabled={!puedeEmitir(estado) || emitir.isPending}
              >
                {emitir.isPending ? (
                  <>
                    <Loader2 className="h-4 w-4 animate-spin" />
                    Emitiendo…
                  </>
                ) : (
                  <>
                    <Undo2 className="h-4 w-4" />
                    Emitir NC
                  </>
                )}
              </Button>
            </div>

            {!puedeEmitir(estado) && !emitir.isPending && (
              <p className="flex items-center gap-1.5 text-xs text-muted-foreground">
                <AlertTriangle className="h-3.5 w-3.5" />
                Indicá cuánto acreditar (sin pasarte del máximo de cada renglón).
              </p>
            )}

            {emitir.error && (
              <p role="alert" className="text-sm font-medium text-destructive">
                {emitir.error.message}
              </p>
            )}
          </div>
        )}
      </div>
    </DialogContent>
  );
}
