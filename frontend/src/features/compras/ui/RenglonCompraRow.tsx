import { Trash2 } from "lucide-react";

import { pesos } from "@/entities/remito/formato";
import { Button } from "@/shared/ui/button";

import type { RenglonCompra } from "../model/estado";

const inputClass =
  "h-9 w-full rounded-md border border-input bg-background px-2 text-sm tabular-nums focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring";

interface Props {
  renglon: RenglonCompra;
  onCampo: (campo: "cantidad" | "costo_unitario", valor: string) => void;
  onQuitar: () => void;
}

export function RenglonCompraRow({ renglon, onCampo, onQuitar }: Props) {
  const subtotal = Number(renglon.cantidad) * Number(renglon.costo_unitario);

  return (
    <div className="grid grid-cols-[1fr_auto] items-center gap-x-3 gap-y-2 p-3 sm:grid-cols-[1fr_4.5rem_7rem_6.5rem_auto]">
      <div className="min-w-0">
        <p className="truncate text-sm font-medium">{renglon.detalle}</p>
        <p className="text-xs text-muted-foreground">{renglon.articulo_codigo}</p>
      </div>

      <input
        aria-label="Cantidad"
        inputMode="decimal"
        value={renglon.cantidad}
        onChange={(e) => onCampo("cantidad", e.target.value)}
        className={inputClass}
      />

      <input
        aria-label="Costo unitario"
        inputMode="decimal"
        value={renglon.costo_unitario}
        onChange={(e) => onCampo("costo_unitario", e.target.value)}
        placeholder="0.00"
        className={inputClass}
      />

      <span className="text-right text-sm font-medium tabular-nums">
        {Number.isFinite(subtotal) && subtotal > 0 ? pesos(String(subtotal)) : "—"}
      </span>

      <Button variant="ghost" size="icon" aria-label="Quitar renglón" onClick={onQuitar}>
        <Trash2 className="h-4 w-4" />
      </Button>
    </div>
  );
}
