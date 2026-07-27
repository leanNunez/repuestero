import { useState } from "react";

import { Button } from "@/shared/ui/button";
import { CampoMoneda } from "@/shared/ui/campo-moneda";
import { Card } from "@/shared/ui/card";

import { CONCEPTOS_MANUALES, FORMAS, etiquetaForma } from "../model/estado";

const campoClass =
  "h-9 w-full rounded-md border border-input bg-background px-3 text-sm focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 focus-visible:ring-offset-background";

interface Props {
  cargando: boolean;
  error: string | null;
  /** Advertencias del último alta: la caja quedó en negativo. NO es un error — la operación se
   *  aceptó — así que se muestra distinto y no reemplaza al formulario. */
  advertencias: readonly string[];
  onRegistrar: (v: {
    concepto: string;
    forma: string;
    monto: string;
    detalle: string | null;
    fecha: string;
  }) => void;
}

function hoy(): string {
  // `toISOString` pasaría por UTC y, después de las 21 hora argentina, daría el día siguiente —
  // exactamente el bug que arregló el PR #42 del lado del backend. Se arma con las partes locales.
  const d = new Date();
  const mes = String(d.getMonth() + 1).padStart(2, "0");
  const dia = String(d.getDate()).padStart(2, "0");
  return `${d.getFullYear()}-${mes}-${dia}`;
}

/** Alta MANUAL de un movimiento: un gasto, un retiro, un aporte.
 *
 * El select ofrece SOLO los conceptos manuales. Los derivados (una cobranza, un pago) los emite el
 * documento que los genera, y ofrecerlos acá invitaría a cargar dos veces la misma plata — que es
 * el desastre que el módulo existe para no repetir. El backend lo rechaza igual, dos veces; esto es
 * para que la persona no llegue a intentarlo.
 *
 * NO se pide "¿ingreso o egreso?": lo determina el concepto. Pedirlo sería pedir que la persona
 * diga dos veces lo mismo, y la segunda vez es la que se contradice. */
export function FormularioMovimiento({ cargando, error, advertencias, onRegistrar }: Props) {
  const [abierto, setAbierto] = useState(false);
  const [concepto, setConcepto] = useState<string>("gasto");
  const [forma, setForma] = useState<string>("efectivo");
  const [monto, setMonto] = useState("");
  const [detalle, setDetalle] = useState("");
  const [fecha, setFecha] = useState(hoy());

  const montoValido = monto !== "" && Number(monto) > 0;

  function enviar(e: React.FormEvent) {
    e.preventDefault();
    if (!montoValido || cargando) return;

    onRegistrar({
      concepto,
      forma,
      monto,
      detalle: detalle.trim() || null,
      fecha,
    });
    setMonto("");
    setDetalle("");
  }

  if (!abierto) {
    return (
      <div className="space-y-2">
        <Button variant="outline" size="sm" onClick={() => setAbierto(true)}>
          Cargar movimiento a mano
        </Button>
        {advertencias.length > 0 && <Advertencias avisos={advertencias} />}
      </div>
    );
  }

  return (
    <Card className="space-y-3 p-3">
      <form onSubmit={enviar} className="space-y-3">
        <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
          <div className="space-y-1">
            <label htmlFor="caja-concepto" className="text-xs text-muted-foreground">
              Concepto
            </label>
            <select
              id="caja-concepto"
              value={concepto}
              onChange={(e) => setConcepto(e.target.value)}
              className={campoClass}
            >
              {CONCEPTOS_MANUALES.map((c) => (
                <option key={c.id} value={c.id}>
                  {c.label}
                </option>
              ))}
            </select>
          </div>

          <div className="space-y-1">
            <label htmlFor="caja-forma" className="text-xs text-muted-foreground">
              Forma
            </label>
            <select
              id="caja-forma"
              value={forma}
              onChange={(e) => setForma(e.target.value)}
              className={campoClass}
            >
              {FORMAS.map((f) => (
                <option key={f} value={f}>
                  {etiquetaForma(f)}
                </option>
              ))}
            </select>
          </div>

          <div className="space-y-1">
            <label htmlFor="caja-monto" className="text-xs text-muted-foreground">
              Monto
            </label>
            <CampoMoneda
              id="caja-monto"
              value={monto}
              onChange={setMonto}
              placeholder="0,00"
              disabled={cargando}
              className={campoClass}
            />
          </div>

          <div className="space-y-1">
            <label htmlFor="caja-fecha" className="text-xs text-muted-foreground">
              Fecha
            </label>
            <input
              id="caja-fecha"
              type="date"
              value={fecha}
              onChange={(e) => setFecha(e.target.value)}
              className={campoClass}
            />
          </div>
        </div>

        <div className="space-y-1">
          <label htmlFor="caja-detalle" className="text-xs text-muted-foreground">
            Detalle (opcional)
          </label>
          <input
            id="caja-detalle"
            value={detalle}
            onChange={(e) => setDetalle(e.target.value)}
            maxLength={200}
            placeholder="Flete Andreani, librería…"
            className={campoClass}
          />
        </div>

        {error && (
          <p role="alert" className="text-sm text-destructive">
            {error}
          </p>
        )}

        <div className="flex gap-2">
          <Button type="submit" size="sm" disabled={!montoValido || cargando}>
            {cargando ? "Guardando…" : "Registrar"}
          </Button>
          <Button type="button" variant="ghost" size="sm" onClick={() => setAbierto(false)}>
            Cerrar
          </Button>
        </div>
      </form>

      {advertencias.length > 0 && <Advertencias avisos={advertencias} />}
    </Card>
  );
}

/** El movimiento se guardó: esto NO es un error. Se muestra en tono de aviso y no bloquea nada,
 *  que es exactamente la regla que aplica el backend. */
function Advertencias({ avisos }: { avisos: readonly string[] }) {
  return (
    <div role="status" className="rounded-md border border-warning bg-warning/10 p-2 text-sm">
      {avisos.map((a) => (
        <p key={a}>{a}</p>
      ))}
    </div>
  );
}
