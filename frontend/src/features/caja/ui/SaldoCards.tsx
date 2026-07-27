import { AlertTriangle } from "lucide-react";

import type { SaldoCaja } from "@/entities/caja/schema";
import { pesos } from "@/entities/remito/formato";
import { cn } from "@/shared/lib/cn";
import { Card } from "@/shared/ui/card";
import { Skeleton } from "@/shared/ui/skeleton";

import { FORMAS, avisoDeNegativo, estaEnNegativo, etiquetaForma } from "../model/estado";

interface Props {
  saldo: SaldoCaja | undefined;
  isLoading: boolean;
}

/** El efectivo grande y las otras formas al lado, con el aviso PERSISTENTE de saldo negativo.
 *
 * El backend ya devuelve `advertencias` cuando una operación deja la caja en rojo, pero eso es un
 * acuse: se lee una vez y se va. El problema, en cambio, queda. Por eso la advertencia también vive
 * acá, calculada del saldo, hasta que alguien la resuelva.
 *
 * `aria-live="polite"` porque el saldo cambia sin que se navegue a ningún lado: al cargar un gasto
 * o cobrar un cheque, el número se actualiza solo y hay que anunciarlo. */
export function SaldoCards({ saldo, isLoading }: Props) {
  if (isLoading || !saldo) {
    return (
      <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
        {FORMAS.map((f) => (
          <Skeleton key={f} className="h-24 w-full" />
        ))}
      </div>
    );
  }

  const enNegativo = FORMAS.filter((f) => estaEnNegativo(saldo.por_forma[f] ?? "0"));

  return (
    <div className="space-y-3">
      {enNegativo.length > 0 && (
        <div
          role="alert"
          className="flex gap-2 rounded-lg border border-warning bg-warning/10 p-3 text-sm"
        >
          <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0 text-warning" aria-hidden="true" />
          <div className="space-y-1">
            {enNegativo.map((f) => (
              <p key={f}>{avisoDeNegativo(f, saldo.por_forma[f] ?? "0")}</p>
            ))}
          </div>
        </div>
      )}

      <div aria-live="polite" className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
        {FORMAS.map((forma) => {
          const valor = saldo.por_forma[forma] ?? "0";
          const negativo = estaEnNegativo(valor);
          const esEfectivo = forma === "efectivo";

          return (
            <Card key={forma} className="p-3">
              <p className="text-xs text-muted-foreground">{etiquetaForma(forma)}</p>
              <p
                className={cn(
                  "mt-1 font-semibold tabular-nums",
                  // El efectivo es LA pregunta de caja —"¿cuánto tiene que haber en el cajón?"— así
                  // que se muestra más grande que el resto.
                  esEfectivo ? "text-2xl" : "text-lg",
                  negativo && "text-destructive",
                )}
              >
                {pesos(valor)}
              </p>
              {esEfectivo && (
                <p className="mt-0.5 text-xs text-muted-foreground">Lo que tiene que haber</p>
              )}
            </Card>
          );
        })}
      </div>
    </div>
  );
}
