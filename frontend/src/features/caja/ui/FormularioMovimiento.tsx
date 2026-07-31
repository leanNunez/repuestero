import { useState } from "react";

import { Button } from "@/shared/ui/button";
import { CampoMoneda } from "@/shared/ui/campo-moneda";
import { Card } from "@/shared/ui/card";
import { Field, FieldError, FieldLabel } from "@/shared/ui/field";
import { Input } from "@/shared/ui/input";
import { NativeSelect } from "@/shared/ui/native-select";
import { WarningList } from "@/shared/ui/warning-list";

import { CONCEPTOS_MANUALES, FORMAS, etiquetaForma } from "../model/estado";

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
        <WarningList avisos={advertencias} />
      </div>
    );
  }

  return (
    <Card className="space-y-3 p-3">
      <form onSubmit={enviar} className="space-y-3">
        <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
          <Field className="gap-1.5">
            <FieldLabel htmlFor="caja-concepto">Concepto</FieldLabel>
            <NativeSelect
              id="caja-concepto"
              value={concepto}
              onChange={(e) => setConcepto(e.target.value)}
            >
              {CONCEPTOS_MANUALES.map((c) => (
                <option key={c.id} value={c.id}>
                  {c.label}
                </option>
              ))}
            </NativeSelect>
          </Field>

          <Field className="gap-1.5">
            <FieldLabel htmlFor="caja-forma">Forma</FieldLabel>
            <NativeSelect id="caja-forma" value={forma} onChange={(e) => setForma(e.target.value)}>
              {FORMAS.map((f) => (
                <option key={f} value={f}>
                  {etiquetaForma(f)}
                </option>
              ))}
            </NativeSelect>
          </Field>

          <Field className="gap-1.5">
            <FieldLabel htmlFor="caja-monto">Monto</FieldLabel>
            <CampoMoneda
              id="caja-monto"
              value={monto}
              onChange={setMonto}
              placeholder="0,00"
              disabled={cargando}
            />
          </Field>

          <Field className="gap-1.5">
            <FieldLabel htmlFor="caja-fecha">Fecha</FieldLabel>
            <Input
              id="caja-fecha"
              type="date"
              value={fecha}
              onChange={(e) => setFecha(e.target.value)}
            />
          </Field>
        </div>

        <Field className="gap-1.5">
          <FieldLabel htmlFor="caja-detalle">Detalle (opcional)</FieldLabel>
          <Input
            id="caja-detalle"
            value={detalle}
            onChange={(e) => setDetalle(e.target.value)}
            maxLength={200}
            placeholder="Flete Andreani, librería…"
          />
        </Field>

        {error && <FieldError>{error}</FieldError>}

        <div className="flex gap-2">
          <Button type="submit" size="sm" disabled={!montoValido || cargando}>
            {cargando ? "Guardando…" : "Registrar"}
          </Button>
          <Button type="button" variant="ghost" size="sm" onClick={() => setAbierto(false)}>
            Cerrar
          </Button>
        </div>
      </form>

      {/* El movimiento se guardó: esto NO es un error. Se muestra en tono de aviso y no bloquea
          nada, que es exactamente la regla que aplica el backend. */}
      <WarningList avisos={advertencias} />
    </Card>
  );
}
