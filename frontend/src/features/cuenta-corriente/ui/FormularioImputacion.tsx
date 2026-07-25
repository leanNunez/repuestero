import { useState } from "react";

import type { Cuenta } from "@/entities/cuenta-corriente/schema";
import { fechaCorta, hoyISO } from "@/shared/lib/format";
import { Button } from "@/shared/ui/button";
import { CampoMoneda } from "@/shared/ui/campo-moneda";
import { Card } from "@/shared/ui/card";

import { montoValido, type Solapa } from "../model/estado";

const inputClass =
  "h-9 w-full rounded-md border border-input bg-background px-3 text-sm text-foreground tabular-nums focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 focus-visible:ring-offset-background disabled:opacity-50";

interface Props {
  tab: Solapa;
  cuenta: Cuenta;
  cargando: boolean;
  error: string | null;
  onImputar: (monto: string, fecha: string) => void;
}

/** Registrar una cobranza (clientes) o un pago (proveedores).
 *
 * Dos campos, así que sigue sin haber reducer: `useState` local y la validación pura en
 * `estado.ts`. La fecha es CUÁNDO ENTRÓ la plata, no cuándo se carga: la del viernes tipeada el
 * lunes va con la del viernes. */
export function FormularioImputacion({ tab, cuenta, cargando, error, onImputar }: Props) {
  const [monto, setMonto] = useState("");
  const hoy = hoyISO();
  const [fecha, setFecha] = useState(hoy);

  const accion = tab === "clientes" ? "Registrar cobranza" : "Registrar pago";
  const puede = montoValido(monto) && fecha !== "" && !cargando;

  function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!puede) return;
    onImputar(monto.trim(), fecha);
    setMonto("");
    setFecha(hoy);
  }

  return (
    <Card className="p-3">
      <form onSubmit={onSubmit} className="flex flex-col gap-2 sm:flex-row sm:items-end">
        <div className="flex-1">
          <label htmlFor="monto-imputacion" className="mb-1 block text-xs text-muted-foreground">
            {tab === "clientes" ? "Monto cobrado" : "Monto pagado"}
          </label>
          <CampoMoneda
            id="monto-imputacion"
            value={monto}
            onChange={setMonto}
            placeholder="0,00"
            disabled={cargando}
            aria-describedby="monto-hint"
            className={inputClass}
          />
          <p id="monto-hint" className="mt-1 text-xs text-muted-foreground">
            Los miles se separan solos; usá coma para los centavos.
          </p>
        </div>

        <div className="sm:w-44">
          <label htmlFor="fecha-imputacion" className="mb-1 block text-xs text-muted-foreground">
            {tab === "clientes" ? "Fecha del cobro" : "Fecha del pago"}
          </label>
          {/* `max` = hoy: no se puede fechar en el futuro, y eso es evidente en el input. El
              mínimo de 90 días NO se replica acá — es política del backend, que devuelve un 422
              con el mensaje puesto. Duplicar esa regla sería repetir la trampa de `reversible`. */}
          <input
            id="fecha-imputacion"
            type="date"
            value={fecha}
            max={hoy}
            onChange={(e) => setFecha(e.target.value)}
            disabled={cargando}
            className={inputClass}
          />
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
        Se imputa a la cuenta de <span className="font-medium">{cuenta.nombre}</span> con fecha{" "}
        <span className="font-medium">{fecha === hoy ? "de hoy" : fechaCorta(fecha)}</span>.
      </p>
    </Card>
  );
}
