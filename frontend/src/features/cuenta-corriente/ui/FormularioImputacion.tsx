import { useState } from "react";

import type { Cuenta } from "@/entities/cuenta-corriente/schema";
import { Button } from "@/shared/ui/button";
import { Card } from "@/shared/ui/card";

import { montoValido, type Solapa } from "../model/estado";

const inputClass =
  "h-9 w-full rounded-md border border-input bg-background px-3 text-sm text-foreground tabular-nums focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 focus-visible:ring-offset-background disabled:opacity-50";

interface Props {
  tab: Solapa;
  cuenta: Cuenta;
  cargando: boolean;
  error: string | null;
  onImputar: (monto: string) => void;
}

/** Registrar una cobranza (clientes) o un pago (proveedores).
 *
 * Un solo campo, así que no hay reducer: `useState` local y la validación pura en `estado.ts`. */
export function FormularioImputacion({ tab, cuenta, cargando, error, onImputar }: Props) {
  const [monto, setMonto] = useState("");

  const accion = tab === "clientes" ? "Registrar cobranza" : "Registrar pago";
  const puede = montoValido(monto) && !cargando;

  function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!puede) return;
    onImputar(monto.trim());
    setMonto("");
  }

  return (
    <Card className="p-3">
      <form onSubmit={onSubmit} className="flex flex-col gap-2 sm:flex-row sm:items-end">
        <div className="flex-1">
          <label htmlFor="monto-imputacion" className="mb-1 block text-xs text-muted-foreground">
            {tab === "clientes" ? "Monto cobrado" : "Monto pagado"}
          </label>
          <input
            id="monto-imputacion"
            value={monto}
            onChange={(e) => setMonto(e.target.value)}
            inputMode="decimal"
            placeholder="0.00"
            disabled={cargando}
            aria-describedby="monto-hint"
            className={inputClass}
          />
          {/* El operador argentino va a tipear coma. `Number("10,50")` es NaN, así que se rechaza
              y el hint es lo que evita que quede peleando con el botón deshabilitado. */}
          <p id="monto-hint" className="mt-1 text-xs text-muted-foreground">
            Usá punto para los centavos: 1250.50
          </p>
        </div>

        <Button type="submit" disabled={!puede} className="shrink-0">
          {cargando ? "Registrando…" : accion}
        </Button>
      </form>

      {error && (
        <p role="alert" className="mt-2 text-sm text-destructive">
          {error}
        </p>
      )}

      <p className="mt-2 text-xs text-muted-foreground">
        Se imputa a la cuenta de <span className="font-medium">{cuenta.nombre}</span> con fecha de
        hoy.
      </p>
    </Card>
  );
}
