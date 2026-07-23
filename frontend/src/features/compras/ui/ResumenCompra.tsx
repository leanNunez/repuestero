import { AlertTriangle, Loader2, Truck } from "lucide-react";

import { pesos } from "@/entities/remito/formato";
import { Button } from "@/shared/ui/button";
import { Card } from "@/shared/ui/card";

import type { Estado, Totales } from "../model/estado";

const inputClass =
  "h-9 w-full rounded-md border border-input bg-background px-3 text-sm focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring";
const selectClass = inputClass;

interface Props {
  estado: Estado;
  tot: Totales;
  onCondicion: (valor: "contado" | "cta_cte") => void;
  onDeposito: (valor: string) => void;
  onEmitir: () => void;
  puede: boolean;
  cargando: boolean;
  error?: string | null;
}

export function ResumenCompra({
  estado,
  tot,
  onCondicion,
  onDeposito,
  onEmitir,
  puede,
  cargando,
  error,
}: Props) {
  const motivo =
    estado.proveedorCodigo.trim().length === 0
      ? "Elegí el proveedor."
      : estado.numeroComprobante.trim().length === 0
        ? "Cargá el número del comprobante del proveedor."
        : estado.renglones.length === 0
          ? "Agregá al menos un artículo."
          : estado.deposito.trim().length === 0
            ? "Indicá el depósito."
            : "Revisá cantidades y costos: hay un renglón incompleto.";

  return (
    <Card className="space-y-4 p-4">
      <div className="grid gap-3 sm:grid-cols-2">
        <div className="space-y-1">
          <label htmlFor="condicion" className="text-xs font-medium">
            Condición
          </label>
          <select
            id="condicion"
            value={estado.condicion}
            onChange={(e) => onCondicion(e.target.value as "contado" | "cta_cte")}
            className={selectClass}
          >
            <option value="contado">Contado</option>
            <option value="cta_cte">Cuenta corriente</option>
          </select>
          <p className="text-[11px] text-muted-foreground">
            A crédito imputa el total a la cuenta corriente del proveedor (lo que le debemos).
          </p>
        </div>

        <div className="space-y-1">
          <label htmlFor="deposito" className="text-xs font-medium">
            Depósito <span className="text-destructive">*</span>
          </label>
          <input
            id="deposito"
            value={estado.deposito}
            onChange={(e) => onDeposito(e.target.value)}
            placeholder="CEN"
            className={inputClass}
          />
          <p className="text-[11px] text-muted-foreground">A dónde entra la mercadería.</p>
        </div>
      </div>

      <div className="flex flex-wrap items-end justify-between gap-3 border-t pt-3">
        <div className="space-y-0.5 text-sm">
          <p className="text-muted-foreground">
            Neto <span className="font-medium text-foreground">{pesos(String(tot.neto))}</span> · IVA{" "}
            <span className="font-medium text-foreground">{pesos(String(tot.iva))}</span>
          </p>
          <p className="text-lg font-semibold tabular-nums">Total {pesos(String(tot.total))}</p>
        </div>

        <Button onClick={onEmitir} disabled={!puede || cargando}>
          {cargando ? (
            <>
              <Loader2 className="h-4 w-4 animate-spin" />
              Registrando…
            </>
          ) : (
            <>
              <Truck className="h-4 w-4" />
              Registrar compra
            </>
          )}
        </Button>
      </div>

      {!puede && !cargando && (
        <p className="flex items-center gap-1.5 text-xs text-muted-foreground">
          <AlertTriangle className="h-3.5 w-3.5" />
          {motivo}
        </p>
      )}

      {error && (
        <p role="alert" className="text-sm font-medium text-destructive">
          {error}
        </p>
      )}
    </Card>
  );
}
