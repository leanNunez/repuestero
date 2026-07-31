import { CheckCircle2 } from "lucide-react";
import type { ReactNode } from "react";

import { cn } from "@/shared/lib/cn";

/** Confirmación PERSISTENTE de una operación con datos que la persona necesita retener
 *  (número de comprobante, total). Por eso es un panel y no un toast: un toast se va y el
 *  número que había que anotar se fue con él (docs/art-direction.md). */
export function SuccessPanel({
  className,
  icon,
  children,
}: {
  className?: string;
  /** Ícono del medallón; por defecto el tilde. */
  icon?: ReactNode;
  children: ReactNode;
}) {
  return (
    <div className={cn("flex flex-col items-center gap-4 text-center", className)}>
      <div className="flex h-16 w-16 items-center justify-center rounded-2xl bg-success/15 text-success dark:bg-success/10">
        {icon ?? <CheckCircle2 className="h-8 w-8" />}
      </div>
      {children}
    </div>
  );
}
