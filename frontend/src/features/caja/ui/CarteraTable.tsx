import type { Cheque } from "@/entities/caja/schema";
import { pesos } from "@/entities/remito/formato";
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

import { etiquetaEstado } from "../model/estado";
import type { Transicion } from "../model/hooks";

/** Qué se puede hacer con un cheque RECIBIDO según su estado, y con qué etiqueta.
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
const RECIBIDO: Record<string, { id: Transicion; label: string }[]> = {
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

/** Un cheque EMITIDO es un papel que firmé yo, no uno que me dieron.
 *
 * No lo deposito ni lo cobro: eso lo hace el proveedor, en su banco. Lo único que puedo registrar
 * es que se lo entregué, y que volvió rechazado si el banco no me lo pagó. Ofrecer "Depositar" o
 * "Cobrar" sobre un cheque propio no describe ninguna operación real. */
const EMITIDO: Record<string, { id: Transicion; label: string }[]> = {
  en_cartera: [
    { id: "entregar", label: "Entregar" },
    { id: "rechazar", label: "Rechazó" },
  ],
};

function accionesDe(cheque: Cheque): { id: Transicion; label: string }[] {
  const tabla = cheque.origen === "emitido" ? EMITIDO : RECIBIDO;
  return tabla[cheque.estado] ?? [];
}

/** Conciliar es cruzar contra el RESUMEN BANCARIO, así que solo tiene sentido en los estados que
 *  pasaron por el banco. Espeja `ESTADOS_CONCILIABLES` del service, que es quien lo hace cumplir con
 *  un 422: un cheque `anulado` o `en_cartera` no puede figurar en ningún resumen. */
const CONCILIABLES = new Set(["depositado", "cobrado", "rechazado"]);

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
  /** Para que la página de altura fija le dé el alto sobrante y scrollee solo el cuerpo. */
  containerClassName?: string;
}

export function CarteraTable({
  cheques,
  isLoading,
  isError,
  onRetry,
  onTransicion,
  onConciliar,
  ocupado,
  containerClassName,
}: Props) {
  if (isLoading) return <TableSkeleton className="h-12 w-full" />;
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
    <Table containerClassName={containerClassName}>
      <TableCaption className="sr-only">
        Cheques de la cartera, ordenados por fecha de cobro
      </TableCaption>
      <TableHeader>
        <TableRow>
          <TableHead scope="col">Cheque</TableHead>
          <TableHead scope="col">Origen</TableHead>
          <TableHead scope="col">Se cobra</TableHead>
          <TableHead scope="col" className="text-right">
            Importe
          </TableHead>
          <TableHead scope="col">Estado</TableHead>
          <TableHead scope="col">
            <span className="sr-only">Acciones</span>
          </TableHead>
        </TableRow>
      </TableHeader>
      <TableBody>
        {cheques.map((c) => {
          const acciones = accionesDe(c);
          const enVuelo = ocupado === c.id;

          return (
            <TableRow key={c.id}>
              <TableCell className="align-top">
                {/* `banco` y `numero` nacen en NULL: un renglón de forma de pago solo trae forma
                    y monto. Hasta que alguien los complete, el id interno es lo único que
                    identifica al papel — y decirlo es mejor que mostrar un campo vacío. */}
                {c.banco ?? <span className="text-muted-foreground">Sin datos</span>}
                <span className="mt-0.5 block text-xs tabular-nums text-muted-foreground">
                  {c.numero ? `N° ${c.numero}` : `#${c.id}`}
                </span>
              </TableCell>
              <TableCell className="align-top text-muted-foreground">
                {c.origen === "recibido" ? "Recibido" : "Emitido"}
              </TableCell>
              <TableCell className="whitespace-nowrap align-top tabular-nums">
                {c.fecha_cobro ? fechaCorta(c.fecha_cobro) : "—"}
              </TableCell>
              <TableCell className="text-right align-top font-medium">
                <Money value={c.importe} centavos />
              </TableCell>
              <TableCell className="align-top">
                <Badge variant={TONO_ESTADO[c.estado] ?? "default"}>
                  {etiquetaEstado(c.estado)}
                </Badge>
                {c.conciliado && (
                  <span className="mt-1 block text-xs text-muted-foreground">Conciliado</span>
                )}
              </TableCell>
              <TableCell className="whitespace-nowrap align-top">
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
                  {!c.conciliado && CONCILIABLES.has(c.estado) && (
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
              </TableCell>
            </TableRow>
          );
        })}
      </TableBody>
    </Table>
  );
}
