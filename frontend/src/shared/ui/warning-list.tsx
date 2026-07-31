import { AlertTriangle } from "lucide-react";

import { cn } from "@/shared/lib/cn";

/** Advertencias que NO bloquean: la operación siguió, pero hay algo para mirar.
 *  `role="status"` y no `alert` justamente por eso — se anuncia sin interrumpir. */
export function WarningList({
  avisos,
  className,
}: {
  avisos: readonly string[];
  className?: string;
}) {
  if (avisos.length === 0) return null;

  return (
    <ul
      role="status"
      className={cn("space-y-1.5 rounded-lg bg-warning/10 p-3 text-left text-sm", className)}
    >
      {avisos.map((a) => (
        <li key={a} className="flex gap-2">
          <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0 text-warning" />
          {a}
        </li>
      ))}
    </ul>
  );
}
