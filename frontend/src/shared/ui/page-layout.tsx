import type { ReactNode } from "react";

import { cn } from "@/shared/lib/cn";

/** Página de ALTURA FIJA: el encabezado, el buscador y el paginador quedan siempre a la
 *  vista, y lo único que scrollea es el cuerpo de datos (la fila que lleve `flex-1`).
 *
 *  Solo desde `sm` para arriba. En un teléfono, fijar cinco bandas —título, alta,
 *  búsqueda, contador y paginación— dejaría la tabla en unos doscientos píxeles: ahí
 *  scrollear la página entera es mejor que ver tres filas. */
export function PageLayout({
  className,
  children,
}: {
  className?: string;
  children: ReactNode;
}) {
  return (
    <div className={cn("flex flex-col gap-4 p-4 sm:h-full sm:min-h-0 md:p-5", className)}>
      {children}
    </div>
  );
}

/** La zona que se come el alto sobrante y scrollea. Va alrededor del bloque de datos
 *  cuando ese bloque no es una sola tabla (por ejemplo, contador + tabla + paginación). */
export function PageBody({
  className,
  children,
}: {
  className?: string;
  children: ReactNode;
}) {
  return (
    <div className={cn("flex flex-col gap-3 sm:min-h-0 sm:flex-1", className)}>{children}</div>
  );
}
