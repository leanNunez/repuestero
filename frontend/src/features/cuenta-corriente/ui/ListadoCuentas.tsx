import type { Cuenta } from "@/entities/cuenta-corriente/schema";
import { cn } from "@/shared/lib/cn";
import { Badge } from "@/shared/ui/badge";
import { Card } from "@/shared/ui/card";
import { Money } from "@/shared/ui/money";
import { Skeleton } from "@/shared/ui/skeleton";
import { EmptyState, ErrorState } from "@/shared/ui/states";

import { excedeLimite, signoSaldo } from "../model/estado";

interface Props {
  cuentas: Cuenta[] | undefined;
  seleccionada: number | null;
  isLoading: boolean;
  isError: boolean;
  /** Si está mostrando también las cuentas en cero: cambia el mensaje del estado vacío. */
  todos: boolean;
  onSeleccionar: (id: number) => void;
  onRetry: () => void;
  /** Para que la columna de altura fija le dé el alto sobrante y scrollee solo la lista. */
  className?: string;
}

export function ListadoCuentas({
  cuentas,
  seleccionada,
  isLoading,
  isError,
  todos,
  onSeleccionar,
  onRetry,
  className,
}: Props) {
  if (isLoading) {
    return (
      <div className="space-y-2">
        {Array.from({ length: 6 }).map((_, i) => (
          <Skeleton key={i} className="h-14 w-full" />
        ))}
      </div>
    );
  }
  if (isError) return <ErrorState onRetry={onRetry} />;
  if (!cuentas || cuentas.length === 0) {
    return (
      <EmptyState
        title={todos ? "No hay cuentas para mostrar" : "Nadie tiene saldo pendiente"}
        hint={
          todos
            ? "Probá con otro texto de búsqueda."
            : "Marcá «Ver todas» para incluir las cuentas en cero."
        }
      />
    );
  }

  return (
    <Card className={cn("divide-y overflow-auto p-0", className)}>
      <ul>
        {cuentas.map((c) => {
          const signo = signoSaldo(c.saldo);
          const excedida = excedeLimite(c.saldo, c.limite);

          return (
            <li key={c.id}>
              <button
                type="button"
                onClick={() => onSeleccionar(c.id)}
                aria-current={c.id === seleccionada ? "true" : undefined}
                className={cn(
                  "flex w-full items-center justify-between gap-3 p-3 text-left text-sm",
                  "hover:bg-muted/50 focus-visible:outline-2 focus-visible:-outline-offset-2 focus-visible:outline-primary",
                  c.id === seleccionada && "bg-muted",
                )}
              >
                <div className="min-w-0">
                  <p className="truncate font-medium">{c.nombre}</p>
                  <p className="truncate text-xs text-muted-foreground tabular-nums">{c.codigo}</p>
                </div>

                <div className="flex shrink-0 flex-col items-end gap-1">
                  <Money
                    value={c.saldo}
                    centavos
                    className={cn("font-medium", signo === "a-favor" && "text-success")}
                  />
                  {/* El color no puede ser el único indicador: un saldo a favor lo dice con
                      texto, no solo pintado de verde. */}
                  {signo === "a-favor" && <span className="text-xs text-muted-foreground">a favor</span>}
                  {excedida && <Badge variant="warning">Excede el límite</Badge>}
                </div>
              </button>
            </li>
          );
        })}
      </ul>
    </Card>
  );
}
