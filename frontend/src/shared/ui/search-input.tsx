import { Search } from "lucide-react";
import type { ComponentProps } from "react";

import { cn } from "@/shared/lib/cn";
import { Input } from "./input";

/** Campo de búsqueda con la lupa adentro: el patrón que repetían los cuatro padrones
 *  y el combobox, cada uno con su propia copia del posicionamiento del ícono. */
export function SearchInput({
  className,
  containerClassName,
  ...props
}: ComponentProps<"input"> & { containerClassName?: string }) {
  return (
    <div className={cn("relative", containerClassName)}>
      <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
      <Input type="search" className={cn("pl-10", className)} {...props} />
    </div>
  );
}
