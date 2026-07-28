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

  // Lo que se MUESTRA por forma. `cheque` no sale del libro: `por_forma.cheque` es el neto de
  // recibidos menos emitidos —un cheque propio resta sin haber sumado nunca— así que rotularlo
  // "Cheques en cartera" era mentir, y podía mostrar un negativo con la cartera llena o vacía. El
  // valor de la cartera viene de la tabla `cheques`.
  const valores = FORMAS.map((forma) => ({
    forma,
    valor: forma === "cheque" ? saldo.cheques_en_cartera : (saldo.por_forma[forma] ?? "0"),
  }));

  // La advertencia se calcula sobre lo que se MUESTRA, no sobre el libro: si mirara
  // `por_forma.cheque` gritaría "negativo" cada vez que hay cheques propios en la calle, que es lo
  // normal. Una alarma que suena siempre es una alarma que nadie mira. El backend hace el mismo
  // recorte en `advertencias_de_saldo`.
  const enNegativo = valores.filter((v) => estaEnNegativo(v.valor));

  return (
    <div className="space-y-3">
      {enNegativo.length > 0 && (
        <div
          role="alert"
          className="flex gap-2 rounded-lg border border-warning bg-warning/10 p-3 text-sm"
        >
          <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0 text-warning" aria-hidden="true" />
          <div className="space-y-1">
            {enNegativo.map(({ forma, valor }) => (
              <p key={forma}>{avisoDeNegativo(forma, valor)}</p>
            ))}
          </div>
        </div>
      )}

      <div aria-live="polite" className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
        {valores.map(({ forma, valor }) => {
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
