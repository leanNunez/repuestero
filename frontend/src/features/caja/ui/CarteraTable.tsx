import type { Cheque } from "@/entities/caja/schema";
import { pesos } from "@/entities/remito/formato";
import { fechaCorta } from "@/shared/lib/format";
import { Badge } from "@/shared/ui/badge";
import { Button } from "@/shared/ui/button";
import { Skeleton } from "@/shared/ui/skeleton";
import { EmptyState, ErrorState } from "@/shared/ui/states";

import { etiquetaEstado } from "../model/estado";
import type { Transicion } from "../model/hooks";

/** Qué se puede hacer con un cheque según su estado, y con qué etiqueta.
 *
 * ## Por qué esto NO es la máquina de estados
 *
 * La máquina de estados vive en `app/caja/service.py` y es la que decide de verdad: si esta tabla
 * ofreciera una transición que el backend rechaza, la respuesta es un 422 legible, no una
 * corrupción. Esto es la lista de BOTONES A DIBUJAR — una comodidad de la pantalla para no ofrecer
 * lo que se sabe que va a fallar.
 *
 * La diferencia importa a la hora de mantenerla: si el backend agrega una transición y acá no se
 * agrega, el botón falta pero nada se rompe. Al revés —que el front invente una transición— el
 * backend la rechaza. En ningún caso el front define la regla.
 *
 * Los estados terminales no aparecen: no tienen salida.
 */
const ACCIONES: Record<string, { id: Transicion; label: string }[]> = {
  en_cartera: [
    { id: "depositar", label: "Depositar" },
    { id: "cobrar", label: "Cobrar" },
    { id: "entregar", label: "Entregar" },
    { id: "rechazar", label: "Rechazar" },
  ],
  depositado: [
    { id: "cobrar", label: "Acreditó" },
    { id: "rechazar", label: "Rebotó" },
  ],
};

const TONO_ESTADO: Record<string, "default" | "warning" | "danger" | "success"> = {
  en_cartera: "default",
  depositado: "warning",
  cobrado: "success",
  rechazado: "danger",
  entregado: "default",
  anulado: "danger",
};

interface Props {
  cheques: Cheque[] | undefined;
  isLoading: boolean;
  isError: boolean;
  onRetry: () => void;
  onTransicion: (cheque: Cheque, transicion: Transicion) => void;
  onConciliar: (cheque: Cheque) => void;
  /** Id del cheque con una operación en vuelo, para deshabilitar solo esa fila. */
  ocupado: number | null;
}

export function CarteraTable({
  cheques,
  isLoading,
  isError,
  onRetry,
  onTransicion,
  onConciliar,
  ocupado,
}: Props) {
  if (isLoading) {
    return (
      <div className="space-y-2">
        {Array.from({ length: 6 }).map((_, i) => (
          <Skeleton key={i} className="h-12 w-full" />
        ))}
      </div>
    );
  }
  if (isError) return <ErrorState onRetry={onRetry} />;
  if (!cheques || cheques.length === 0) {
    return (
      <EmptyState
        title="No hay cheques"
        hint="Los cheques entran a la cartera solos cuando se cobra un recibo con forma de pago cheque."
      />
    );
  }

  return (
    <div className="overflow-x-auto rounded-lg border border-border bg-card">
      <table className="w-full text-left text-sm">
        <caption className="sr-only">
          Cheques de la cartera, ordenados por fecha de cobro
        </caption>
        <thead className="border-b border-border text-xs text-muted-foreground">
          <tr>
            <th scope="col" className="px-4 py-2.5 font-medium">
              Cheque
            </th>
            <th scope="col" className="px-4 py-2.5 font-medium">
              Origen
            </th>
            <th scope="col" className="px-4 py-2.5 font-medium">
              Se cobra
            </th>
            <th scope="col" className="px-4 py-2.5 text-right font-medium">
              Importe
            </th>
            <th scope="col" className="px-4 py-2.5 font-medium">
              Estado
            </th>
            <th scope="col" className="px-4 py-2.5 font-medium">
              <span className="sr-only">Acciones</span>
            </th>
          </tr>
        </thead>
        <tbody>
          {cheques.map((c) => {
            const acciones = ACCIONES[c.estado] ?? [];
            const enVuelo = ocupado === c.id;

            return (
              <tr key={c.id} className="border-b border-border last:border-0 hover:bg-muted/50">
                <td className="px-4 py-2.5 align-top">
                  {/* `banco` y `numero` nacen en NULL: un renglón de forma de pago solo trae forma
                      y monto. Hasta que alguien los complete, el id interno es lo único que
                      identifica al papel — y decirlo es mejor que mostrar un campo vacío. */}
                  {c.banco ?? <span className="text-muted-foreground">Sin datos</span>}
                  <span className="mt-0.5 block text-xs text-muted-foreground tabular-nums">
                    {c.numero ? `N° ${c.numero}` : `#${c.id}`}
                  </span>
                </td>
                <td className="px-4 py-2.5 align-top text-muted-foreground">
                  {c.origen === "recibido" ? "Recibido" : "Emitido"}
                </td>
                <td className="whitespace-nowrap px-4 py-2.5 align-top tabular-nums">
                  {c.fecha_cobro ? fechaCorta(c.fecha_cobro) : "—"}
                </td>
                <td className="px-4 py-2.5 text-right align-top font-medium tabular-nums">
                  {pesos(c.importe)}
                </td>
                <td className="px-4 py-2.5 align-top">
                  <Badge variant={TONO_ESTADO[c.estado] ?? "default"}>
                    {etiquetaEstado(c.estado)}
                  </Badge>
                  {c.conciliado && (
                    <span className="mt-1 block text-xs text-muted-foreground">Conciliado</span>
                  )}
                </td>
                <td className="whitespace-nowrap px-4 py-2.5 align-top">
                  <div className="flex flex-wrap gap-1">
                    {acciones.map((a) => (
                      <Button
                        key={a.id}
                        variant="ghost"
                        size="sm"
                        disabled={enVuelo}
                        onClick={() => onTransicion(c, a.id)}
                        aria-label={`${a.label} el cheque de ${pesos(c.importe)}`}
                      >
                        {a.label}
                      </Button>
                    ))}
                    {!c.conciliado && (
                      <Button
                        variant="ghost"
                        size="sm"
                        disabled={enVuelo}
                        onClick={() => onConciliar(c)}
                        aria-label={`Conciliar el cheque de ${pesos(c.importe)}`}
                      >
                        Conciliar
                      </Button>
                    )}
                  </div>
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}
