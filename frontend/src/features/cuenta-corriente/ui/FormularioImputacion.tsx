import { useState } from "react";

import type { Cuenta } from "@/entities/cuenta-corriente/schema";
import { fechaCorta, hoyISO } from "@/shared/lib/format";
import { Button } from "@/shared/ui/button";
import { CampoMoneda } from "@/shared/ui/campo-moneda";
import { Card } from "@/shared/ui/card";
import { Input } from "@/shared/ui/input";
import { NativeSelect } from "@/shared/ui/native-select";

import {
  agregarForma,
  cambiarForma,
  cambiarMontoForma,
  etiquetaForma,
  FORMAS,
  formasCierran,
  formasIniciales,
  montoValido,
  quitarForma,
  type Forma,
  type FormaPagoRenglon,
  type Solapa,
} from "../model/estado";


interface Props {
  tab: Solapa;
  cuenta: Cuenta;
  cargando: boolean;
  error: string | null;
  onImputar: (monto: string, fecha: string, formasPago: FormaPagoRenglon[]) => void;
}

/** Registrar una cobranza (clientes) o un pago (proveedores), con su detalle de formas de pago.
 *
 * El caso común del mostrador sigue siendo el de antes: tipear el monto y apretar Enter. Mientras
 * haya UNA sola forma, su importe espeja el total automáticamente y el operador no lo toca — no
 * tiene sentido pedirle que escriba el mismo número dos veces.
 *
 * El pago mixto (5.000 en efectivo y un cheque por 15.000) está a un click: "Agregar forma de pago"
 * parte el detalle en dos y recién ahí los importes se editan. Es VISIBLE y no está escondido
 * detrás de un "detallar", porque es un caso real y frecuente, no una excepción.
 *
 * Sigue sin haber reducer, igual que antes: los renglones son un `useState` y toda la lógica de
 * agregar/quitar/repartir vive pura en `estado.ts`, donde se testea sin montar nada. */
export function FormularioImputacion({ tab, cuenta, cargando, error, onImputar }: Props) {
  const [monto, setMonto] = useState("");
  const hoy = hoyISO();
  const [fecha, setFecha] = useState(hoy);
  const [formas, setFormas] = useState<FormaPagoRenglon[]>(() => formasIniciales(""));

  const esClientes = tab === "clientes";
  const accion = esClientes ? "Registrar cobranza" : "Registrar pago";
  const unaSola = formas.length === 1;

  // Con una sola forma, su importe ES el monto: el operador no lo tipea dos veces. Con dos o más,
  // manda lo que él repartió y el submit espera a que cierre.
  const detalle: FormaPagoRenglon[] = unaSola ? [{ ...formas[0], monto }] : formas;
  const puede = montoValido(monto) && fecha !== "" && formasCierran(detalle, monto) && !cargando;

  function limpiar() {
    setMonto("");
    setFecha(hoy);
    setFormas(formasIniciales(""));
  }

  function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!puede) return;
    onImputar(monto.trim(), fecha, detalle);
    limpiar();
  }

  return (
    <Card className="p-3">
      <form onSubmit={onSubmit} className="flex flex-col gap-3">
        <div className="flex flex-col gap-2 sm:flex-row sm:items-end">
          <div className="flex-1">
            <label htmlFor="monto-imputacion" className="mb-1 block text-xs text-muted-foreground">
              {esClientes ? "Monto cobrado" : "Monto pagado"}
            </label>
            <CampoMoneda
              id="monto-imputacion"
              value={monto}
              onChange={setMonto}
              placeholder="0,00"
              disabled={cargando}
              aria-describedby="monto-hint"
              className="text-right"
            />
            <p id="monto-hint" className="mt-1 text-xs text-muted-foreground">
              Los miles se separan solos; usá coma para los centavos.
            </p>
          </div>

          <div className="sm:w-44">
            <label htmlFor="fecha-imputacion" className="mb-1 block text-xs text-muted-foreground">
              {esClientes ? "Fecha del cobro" : "Fecha del pago"}
            </label>
            {/* `max` = hoy: no se puede fechar en el futuro, y eso es evidente en el input. El
                mínimo de 90 días NO se replica acá — es política del backend, que devuelve un 422
                con el mensaje puesto. Duplicar esa regla sería repetir la trampa de `reversible`. */}
            <Input
              id="fecha-imputacion"
              type="date"
              value={fecha}
              max={hoy}
              onChange={(e) => setFecha(e.target.value)}
              disabled={cargando}
              className="tabular-nums"
            />
          </div>

          <Button type="submit" disabled={!puede} className="shrink-0">
            {cargando ? "Registrando…" : accion}
          </Button>
        </div>

        <fieldset className="border-t border-border pt-2">
          <legend className="sr-only">
            {esClientes ? "Con qué se cobró" : "Con qué se pagó"}
          </legend>

          <div className="flex flex-col gap-2">
            {formas.map((renglon, i) => (
              // El índice como key: la lista es corta, se ordena por posición y no hay id estable
              // —estos renglones todavía no existen en la base—. Quitar uno del medio remonta los
              // de abajo, que es aceptable acá: son dos o tres campos sin estado propio.
              <div key={i} className="flex items-end gap-2">
                <div className="flex-1">
                  <label
                    htmlFor={`forma-pago-${i}`}
                    className="mb-1 block text-xs text-muted-foreground"
                  >
                    {i === 0 ? (esClientes ? "Con qué te pagó" : "Con qué le pagaste") : "Y además"}
                  </label>
                  <NativeSelect
                    id={`forma-pago-${i}`}
                    value={renglon.forma}
                    onChange={(e) => setFormas(cambiarForma(formas, i, e.target.value as Forma))}
                    disabled={cargando}
                  >
                    {FORMAS.map((f) => (
                      <option key={f} value={f}>
                        {etiquetaForma(f)}
                      </option>
                    ))}
                  </NativeSelect>
                </div>

                {/* Con una sola forma el importe no se muestra: es el monto de arriba. */}
                {!unaSola && (
                  <>
                    <div className="w-32">
                      <label
                        htmlFor={`monto-forma-${i}`}
                        className="mb-1 block text-xs text-muted-foreground"
                      >
                        Importe
                      </label>
                      <CampoMoneda
                        id={`monto-forma-${i}`}
                        value={renglon.monto}
                        onChange={(v) => setFormas(cambiarMontoForma(formas, i, v))}
                        placeholder="0,00"
                        disabled={cargando}
                        className="text-right"
                      />
                    </div>
                    <Button
                      type="button"
                      variant="ghost"
                      onClick={() => setFormas(quitarForma(formas, i))}
                      disabled={cargando}
                      className="shrink-0"
                    >
                      Quitar
                    </Button>
                  </>
                )}
              </div>
            ))}
          </div>

          <div className="mt-2 flex items-center gap-3">
            <Button
              type="button"
              variant="ghost"
              onClick={() => setFormas(agregarForma(detalle, monto))}
              disabled={cargando}
            >
              + Agregar forma de pago
            </Button>

            {/* Solo molesta cuando hay algo que repartir: con una sola forma nunca puede no cerrar. */}
            {!unaSola && !formasCierran(detalle, monto) && (
              <p className="text-xs text-destructive">
                Los importes tienen que sumar el monto de arriba.
              </p>
            )}
          </div>
        </fieldset>
      </form>

      {error && (
        <p role="alert" className="mt-2 text-sm text-destructive">
          {error}
        </p>
      )}

      <p className="mt-2 text-xs text-muted-foreground">
        Se imputa a la cuenta de <span className="font-medium">{cuenta.nombre}</span> con fecha{" "}
        <span className="font-medium">{fecha === hoy ? "de hoy" : fechaCorta(fecha)}</span>, y se
        emite {esClientes ? "un recibo" : "una orden de pago"}.
      </p>
    </Card>
  );
}
