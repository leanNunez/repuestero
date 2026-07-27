import { useState } from "react";

import type { Cheque } from "@/entities/caja/schema";
import { pesos } from "@/entities/remito/formato";
import { Button } from "@/shared/ui/button";
import { Card } from "@/shared/ui/card";

interface Props {
  /** `null` = cerrado. */
  cheque: Cheque | null;
  cargando: boolean;
  error: string | null;
  onCerrar: () => void;
  onConciliar: (fecha: string) => void;
}

function hoy(): string {
  // Sin `toISOString`: pasaría por UTC y después de las 21 hora argentina daría el día siguiente.
  const d = new Date();
  const mes = String(d.getMonth() + 1).padStart(2, "0");
  const dia = String(d.getDate()).padStart(2, "0");
  return `${d.getFullYear()}-${mes}-${dia}`;
}

/** Conciliar un cheque contra el resumen bancario.
 *
 * Es un panel inline y no un modal, igual que `FormularioAjuste` en cuenta corriente: la tabla de
 * atrás es el contexto de lo que se está por hacer, y taparla con un modal lo quita justo cuando
 * hace falta.
 *
 * La fecha es OBLIGATORIA y por eso viene precargada con hoy en vez de vacía: una conciliación sin
 * fecha no se puede auditar —el CHECK de la base la exige igual— y dejar el campo vacío solo lograría
 * un viaje de ida y vuelta al servidor para que diga lo que ya sabemos. */
export function FormularioConciliar({ cheque, cargando, error, onCerrar, onConciliar }: Props) {
  const [fecha, setFecha] = useState(hoy());

  if (!cheque) return null;

  return (
    <Card className="space-y-3 p-3">
      <form
        onSubmit={(e) => {
          e.preventDefault();
          if (!cargando) onConciliar(fecha);
        }}
        className="space-y-3"
      >
        <p className="text-sm">
          Conciliar el cheque de{" "}
          <span className="font-medium tabular-nums">{pesos(cheque.importe)}</span>
          {cheque.banco && <> de {cheque.banco}</>}
        </p>

        <div className="space-y-1">
          <label htmlFor="conciliar-fecha" className="text-xs text-muted-foreground">
            Fecha de conciliación
          </label>
          <input
            id="conciliar-fecha"
            type="date"
            value={fecha}
            onChange={(e) => setFecha(e.target.value)}
            required
            className="h-9 w-full max-w-xs rounded-md border border-input bg-background px-3 text-sm focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 focus-visible:ring-offset-background"
          />
        </div>

        {error && (
          <p role="alert" className="text-sm text-destructive">
            {error}
          </p>
        )}

        <div className="flex gap-2">
          <Button type="submit" size="sm" disabled={cargando}>
            {cargando ? "Guardando…" : "Conciliar"}
          </Button>
          <Button type="button" variant="ghost" size="sm" onClick={onCerrar}>
            Cancelar
          </Button>
        </div>
      </form>
    </Card>
  );
}
