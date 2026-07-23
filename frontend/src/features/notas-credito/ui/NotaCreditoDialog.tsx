import { AlertTriangle, CheckCircle2, Loader2, Undo2, X } from "lucide-react";
import { useEffect, useReducer, useRef } from "react";

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
import { Skeleton } from "@/shared/ui/skeleton";
import { EmptyState, ErrorState } from "@/shared/ui/states";

const inputClass =
  "h-9 w-24 rounded-md border border-input bg-background px-3 text-sm tabular-nums focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring";

function comprobanteLabel(tipo: string, ptoVenta: number, numero: number): string {
  return `${tipo} ${String(ptoVenta).padStart(4, "0")}-${String(numero).padStart(8, "0")}`;
}

interface Props {
  venta: VentaLeer | null;
  onClose: () => void;
}

/** Diálogo para emitir una nota de crédito sobre una venta. El cuerpo se monta fresco por cada
 * apertura (keyed por `venta.id`): así reabrir la misma venta re-inicializa el estado desde los
 * acreditables, aunque React Query devuelva la data cacheada con la misma referencia. */
export function NotaCreditoDialog({ venta, onClose }: Props) {
  if (!venta) return null;
  return <Contenido key={venta.id} venta={venta} onClose={onClose} />;
}

/** Precarga cada renglón en su máximo acreditable (anulación total por defecto); el operador baja
 * las cantidades para una parcial. */
function Contenido({ venta, onClose }: { venta: VentaLeer; onClose: () => void }) {
  const [estado, dispatch] = useReducer(reducer, ESTADO_INICIAL);
  const acreditables = useRenglonesAcreditables(venta.id);
  const emitir = useEmitirNotaCredito();
  const panelRef = useRef<HTMLDivElement>(null);

  // Al llegar los renglones acreditables, arma el estado inicial.
  useEffect(() => {
    if (acreditables.data)
      dispatch({ type: "init", renglones: desdeAcreditables(acreditables.data) });
  }, [acreditables.data]);

  // Escape cierra; foco al panel al abrir.
  useEffect(() => {
    panelRef.current?.focus();
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [onClose]);

  const label = comprobanteLabel(venta.tipo, venta.pto_venta, venta.numero);
  const tot = totales(estado.renglones);

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center p-4"
      role="presentation"
      onClick={onClose}
    >
      <div className="fixed inset-0 bg-black/40" aria-hidden />
      <div
        ref={panelRef}
        role="dialog"
        aria-modal="true"
        aria-labelledby="nc-titulo"
        tabIndex={-1}
        onClick={(e) => e.stopPropagation()}
        className="relative z-10 flex max-h-[90vh] w-full max-w-lg flex-col overflow-hidden rounded-2xl border border-border bg-background shadow-xl focus-visible:outline-none"
      >
        <div className="flex items-start justify-between gap-3 border-b border-border p-4">
          <div>
            <h2 id="nc-titulo" className="text-base font-semibold">
              Nota de crédito
            </h2>
            <p className="text-xs text-muted-foreground">
              Sobre <span className="tabular-nums">{label}</span> · Total {pesos(venta.total)}
            </p>
          </div>
          <Button variant="ghost" size="icon" onClick={onClose} aria-label="Cerrar">
            <X className="h-4 w-4" />
          </Button>
        </div>

        <div className="min-h-0 flex-1 overflow-y-auto p-4">
          {emitir.data ? (
            <div className="flex flex-col items-center gap-4 py-6 text-center">
              <div className="flex h-14 w-14 items-center justify-center rounded-2xl bg-emerald-100 text-emerald-700 dark:bg-emerald-950 dark:text-emerald-400">
                <CheckCircle2 className="h-7 w-7" />
              </div>
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
            </div>
          ) : acreditables.isLoading ? (
            <div className="space-y-2">
              {Array.from({ length: 3 }).map((_, i) => (
                <Skeleton key={i} className="h-12 w-full" />
              ))}
            </div>
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
                  <div
                    key={r.articulo_codigo}
                    className="flex items-center justify-between gap-3 p-3"
                  >
                    <div className="min-w-0">
                      <p className="truncate text-sm font-medium">{r.descripcion}</p>
                      <p className="text-xs text-muted-foreground tabular-nums">
                        {r.articulo_codigo} · {pesos(r.precio_unitario)} c/u · hasta{" "}
                        {r.cantidad_acreditable}
                      </p>
                    </div>
                    <input
                      type="text"
                      inputMode="decimal"
                      value={r.cantidad_acreditar}
                      onChange={(e) => dispatch({ type: "cantidad", i, valor: e.target.value })}
                      aria-label={`Cantidad a acreditar de ${r.descripcion}`}
                      className={inputClass}
                    />
                  </div>
                ))}
              </div>

              <div className="flex flex-wrap items-end justify-between gap-3 border-t border-border pt-3">
                <div className="space-y-0.5 text-sm">
                  <p className="text-muted-foreground">
                    Neto <span className="font-medium text-foreground">{pesos(String(tot.neto))}</span>{" "}
                    · IVA{" "}
                    <span className="font-medium text-foreground">{pesos(String(tot.iva))}</span>
                  </p>
                  <p className="text-lg font-semibold tabular-nums">
                    Total {pesos(String(tot.total))}
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
      </div>
    </div>
  );
}
