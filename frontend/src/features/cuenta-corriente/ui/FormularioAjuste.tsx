import { useState } from "react";

import { pesos } from "@/entities/remito/formato";
import { Button } from "@/shared/ui/button";
import { CampoMoneda } from "@/shared/ui/campo-moneda";
import { Card } from "@/shared/ui/card";
import { Textarea } from "@/shared/ui/textarea";

import {
  espejoDelMovimiento,
  etiquetaTipo,
  montoValido,
  motivoValido,
  type AjustePayload,
  type ModoAjuste,
} from "../model/estado";

const inputClass =
  "h-9 w-full rounded-md border border-input bg-background px-3 text-sm text-foreground tabular-nums focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 focus-visible:ring-offset-background disabled:opacity-50";

type Columna = "debe" | "haber";

interface Props {
  /** `null` = cerrado: solo se ve el botón que lo abre. */
  modo: ModoAjuste | null;
  cargando: boolean;
  error: string | null;
  onAbrir: () => void;
  onCerrar: () => void;
  onAjustar: (payload: AjustePayload) => void;
}

/** Corregir la cuenta corriente. UN formulario con dos modos, espejando el endpoint.
 *
 * - **Reversa**: el importe NO se pide — lo calcula el backend leyendo el movimiento original. Acá
 *   solo se muestra qué contra-asiento va a entrar, y se pide el motivo.
 * - **Manual**: importe en Debe o en Haber, para saldo inicial de migración o condonación.
 *
 * Arranca cerrado a propósito: es la operación peligrosa de la pantalla, no puede ser lo primero
 * que se ve. Y NO abre un modal: `shared/ui` no tiene Dialog, y uno hecho a mano necesita focus
 * trap, Escape y `aria-modal` bien resueltos — es un primitivo de accesibilidad, no un detalle de
 * esta pantalla. */
export function FormularioAjuste({
  modo,
  cargando,
  error,
  onAbrir,
  onCerrar,
  onAjustar,
}: Props) {
  const [motivo, setMotivo] = useState("");
  const [columna, setColumna] = useState<Columna>("debe");
  const [importe, setImporte] = useState("");

  if (modo === null) {
    return (
      <Button variant="outline" size="sm" onClick={onAbrir}>
        Ajustar cuenta
      </Button>
    );
  }

  // Capturado en una const después del guard: el narrowing de un parámetro no sobrevive dentro de
  // los callbacks, y `modo!` en el submit sería una promesa que el compilador no puede sostener.
  const actual = modo;
  const esStorno = actual.kind === "storno";
  const espejo = actual.kind === "storno" ? espejoDelMovimiento(actual.movimiento) : null;

  // En reversa el importe no se tipea, así que no se valida: alcanza el motivo.
  const puede = motivoValido(motivo) && (esStorno || montoValido(importe)) && !cargando;

  function limpiar() {
    setMotivo("");
    setImporte("");
    setColumna("debe");
  }

  function cerrar() {
    limpiar();
    onCerrar();
  }

  function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!puede) return;

    onAjustar(
      actual.kind === "storno"
        ? { motivo: motivo.trim(), revierte_movimiento_id: actual.movimiento.id }
        : { motivo: motivo.trim(), [columna]: importe.trim() },
    );
    limpiar();
  }

  return (
    <Card className="border-amber-300/60 p-3 dark:border-amber-800/60">
      <form onSubmit={onSubmit} className="space-y-3">
        <div className="flex items-start justify-between gap-2">
          <div className="min-w-0">
            <h3 className="text-sm font-medium">
              {esStorno ? "Revertir un movimiento" : "Ajuste manual"}
            </h3>
            <p className="mt-0.5 text-xs text-muted-foreground">
              {esStorno
                ? "No se edita el movimiento original: entra un contra-asiento nuevo."
                : "Para saldo inicial, condonación o redondeo. El importe lo pones vos."}
            </p>
          </div>
          <Button type="button" variant="ghost" size="sm" onClick={cerrar} disabled={cargando}>
            Cancelar
          </Button>
        </div>

        {espejo && actual.kind === "storno" && (
          <p className="rounded-md bg-muted px-3 py-2 text-sm">
            Se revierte {etiquetaTipo(actual.movimiento.tipo).toLowerCase()} #
            {actual.movimiento.id} con un <span className="font-medium">{espejo.columna}</span> de{" "}
            <span className="font-medium tabular-nums">{pesos(espejo.importe)}</span>.
            {/* El importe que vale lo calcula el backend leyendo el original: esto es un espejo
                de cortesía para que la persona vea qué va a pasar antes de confirmar. */}
          </p>
        )}

        {!esStorno && (
          <div className="flex flex-col gap-2 sm:flex-row sm:items-end">
            <div>
              <label
                htmlFor="ajuste-columna"
                className="mb-1 block text-xs text-muted-foreground"
              >
                Columna
              </label>
              <select
                id="ajuste-columna"
                value={columna}
                onChange={(e) => setColumna(e.target.value as Columna)}
                disabled={cargando}
                className={inputClass}
              >
                <option value="debe">Debe (sube la deuda)</option>
                <option value="haber">Haber (baja la deuda)</option>
              </select>
            </div>

            <div className="flex-1">
              <label htmlFor="ajuste-importe" className="mb-1 block text-xs text-muted-foreground">
                Importe
              </label>
              <CampoMoneda
                id="ajuste-importe"
                value={importe}
                onChange={setImporte}
                placeholder="0,00"
                disabled={cargando}
                className={inputClass}
              />
            </div>
          </div>
        )}

        <div>
          <label htmlFor="ajuste-motivo" className="mb-1 block text-xs text-muted-foreground">
            Motivo
          </label>
          <Textarea
            id="ajuste-motivo"
            value={motivo}
            onChange={(e) => setMotivo(e.target.value)}
            placeholder="Por qué se ajusta esta cuenta"
            maxLength={200}
            disabled={cargando}
            aria-describedby="ajuste-motivo-hint"
          />
          <p id="ajuste-motivo-hint" className="mt-1 text-xs text-muted-foreground">
            Obligatorio. Queda guardado en el movimiento: es lo único que va a explicar esta
            corrección en seis meses.
          </p>
        </div>

        <Button type="submit" disabled={!puede}>
          {cargando ? "Registrando…" : esStorno ? "Confirmar reversa" : "Registrar ajuste"}
        </Button>
      </form>

      {error && (
        <p role="alert" className="mt-2 text-sm text-destructive">
          {error}
        </p>
      )}
    </Card>
  );
}
