import { useState } from "react";

import type { Movimiento } from "@/entities/cuenta-corriente/schema";
import { pesos } from "@/entities/remito/formato";
import { Button } from "@/shared/ui/button";
import { Card } from "@/shared/ui/card";
import { Textarea } from "@/shared/ui/textarea";

interface Props {
  /** `null` = cerrado. */
  movimiento: Movimiento | null;
  cargando: boolean;
  error: string | null;
  onCerrar: () => void;
  onAnular: (motivo: string) => void;
}

/** Anular el recibo o la orden de pago de una fila del extracto.
 *
 * ## Por qué pide motivo y no es un "¿estás seguro?"
 *
 * Porque el backend lo exige (`AnulacionCrear`), y lo exige por una razón: la anulación deja rastro
 * en un ledger append-only. Dentro de seis meses, la pregunta que alguien va a hacerse mirando el
 * extracto no es "¿esto se anuló?" —eso se ve— sino **por qué**. Un "¿estás seguro?" no responde
 * nada y encima entrena a la gente a apretar Aceptar sin leer.
 *
 * ## Qué revierte
 *
 * Las TRES cosas que el documento movió —cuenta corriente, caja y cartera— en una sola transacción
 * del lado del servidor. Es lo que reemplazó a "Revertir" en estas filas: revertir tocaba solo el
 * ledger y dejaba vivos el ingreso de caja y el cheque. */
export function FormularioAnulacion({ movimiento, cargando, error, onCerrar, onAnular }: Props) {
  const [motivo, setMotivo] = useState("");

  if (!movimiento) return null;

  const valido = motivo.trim().length > 0;
  const documento = movimiento.ref_tipo === "recibo" ? "recibo" : "orden de pago";
  const importe = Number(movimiento.haber) > 0 ? movimiento.haber : movimiento.debe;

  return (
    <Card className="space-y-3 border-warning p-3">
      <form
        onSubmit={(e) => {
          e.preventDefault();
          if (valido && !cargando) onAnular(motivo.trim());
        }}
        className="space-y-3"
      >
        <div>
          <h3 className="text-sm font-medium">
            Anular {documento} #{movimiento.ref_id}
          </h3>
          <p className="mt-0.5 text-xs text-muted-foreground">
            Se revierte el movimiento de <span className="tabular-nums">{pesos(importe)}</span> en la
            cuenta corriente, en la caja y en la cartera de cheques.
          </p>
        </div>

        <div className="space-y-1">
          <label htmlFor="anulacion-motivo" className="text-xs text-muted-foreground">
            Motivo
          </label>
          <Textarea
            id="anulacion-motivo"
            value={motivo}
            onChange={(e) => setMotivo(e.target.value)}
            rows={2}
            maxLength={300}
            placeholder="Se cargó el importe equivocado…"
            required
          />
        </div>

        {error && (
          <p role="alert" className="text-sm text-destructive">
            {error}
          </p>
        )}

        <div className="flex gap-2">
          <Button type="submit" size="sm" disabled={!valido || cargando}>
            {cargando ? "Anulando…" : "Anular"}
          </Button>
          <Button type="button" variant="ghost" size="sm" onClick={onCerrar}>
            Cancelar
          </Button>
        </div>
      </form>
    </Card>
  );
}
