import { AlertTriangle, Loader2, Receipt } from "lucide-react";

import { Button } from "@/shared/ui/button";
import { Card } from "@/shared/ui/card";
import { Field, FieldDescription, FieldLabel } from "@/shared/ui/field";
import { Input } from "@/shared/ui/input";
import { Money } from "@/shared/ui/money";
import { NativeSelect } from "@/shared/ui/native-select";

import type { Estado, Totales } from "../model/estado";

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

export function ResumenVenta({
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
    estado.clienteCodigo.trim().length === 0
      ? "Elegí el cliente."
      : estado.renglones.length === 0
        ? "Agregá al menos un artículo."
        : estado.deposito.trim().length === 0
          ? "Indicá el depósito."
          : "Revisá cantidades y precios: hay un renglón incompleto.";

  return (
    <Card className="space-y-4 p-4">
      <div className="grid gap-3 sm:grid-cols-2">
        <Field className="gap-1.5">
          <FieldLabel htmlFor="condicion" className="text-xs">
            Condición
          </FieldLabel>
          <NativeSelect
            id="condicion"
            value={estado.condicion}
            onChange={(e) => onCondicion(e.target.value as "contado" | "cta_cte")}
          >
            <option value="contado">Contado</option>
            <option value="cta_cte">Cuenta corriente</option>
          </NativeSelect>
          <FieldDescription className="text-[11px]">
            A crédito imputa el total a la cuenta corriente del cliente.
          </FieldDescription>
        </Field>

        <Field className="gap-1.5">
          <FieldLabel htmlFor="deposito" className="text-xs">
            Depósito <span className="text-destructive">*</span>
          </FieldLabel>
          <Input
            id="deposito"
            value={estado.deposito}
            onChange={(e) => onDeposito(e.target.value)}
            placeholder="CEN"
          />
          <FieldDescription className="text-[11px]">
            De dónde sale la mercadería.
          </FieldDescription>
        </Field>
      </div>

      <div className="flex flex-wrap items-end justify-between gap-3 border-t pt-3">
        <div className="space-y-0.5 text-sm">
          <p className="text-muted-foreground">
            Neto <Money value={tot.neto} centavos className="font-medium text-foreground" /> · IVA{" "}
            <Money value={tot.iva} centavos className="font-medium text-foreground" />
          </p>
          <p className="text-lg font-semibold">
            Total <Money value={tot.total} centavos />
          </p>
        </div>

        <Button onClick={onEmitir} disabled={!puede || cargando}>
          {cargando ? (
            <>
              <Loader2 className="h-4 w-4 animate-spin" />
              Emitiendo…
            </>
          ) : (
            <>
              <Receipt className="h-4 w-4" />
              Emitir venta
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
