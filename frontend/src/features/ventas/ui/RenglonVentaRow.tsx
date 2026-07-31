import { Trash2 } from "lucide-react";

import { Button } from "@/shared/ui/button";
import { CampoMoneda } from "@/shared/ui/campo-moneda";
import { Input } from "@/shared/ui/input";
import { Money } from "@/shared/ui/money";

import type { RenglonVenta } from "../model/estado";

interface Props {
  renglon: RenglonVenta;
  onCampo: (campo: "cantidad" | "precio_unitario", valor: string) => void;
  onQuitar: () => void;
}

export function RenglonVentaRow({ renglon, onCampo, onQuitar }: Props) {
  const subtotal = Number(renglon.cantidad) * Number(renglon.precio_unitario);

  return (
    <div className="grid grid-cols-[1fr_auto] items-center gap-x-3 gap-y-2 p-3 sm:grid-cols-[1fr_4.5rem_7rem_6.5rem_auto]">
      <div className="min-w-0">
        <p className="truncate text-sm font-medium">{renglon.detalle}</p>
        <p className="text-xs text-muted-foreground">
          {renglon.articulo_codigo}
          {renglon.lista_codigo ? ` · lista ${renglon.lista_codigo}` : ""}
        </p>
      </div>

      <Input
        aria-label="Cantidad"
        inputMode="decimal"
        value={renglon.cantidad}
        onChange={(e) => onCampo("cantidad", e.target.value)}
        className="px-2 text-right font-mono tabular-nums"
      />

      <CampoMoneda
        aria-label="Precio unitario"
        value={renglon.precio_unitario}
        onChange={(v) => onCampo("precio_unitario", v)}
        placeholder="0,00"
        className="px-2 text-right font-mono"
      />

      <span className="text-right text-sm font-medium">
        <Money value={Number.isFinite(subtotal) && subtotal > 0 ? subtotal : null} centavos />
      </span>

      <Button variant="ghost" size="icon" aria-label="Quitar renglón" onClick={onQuitar}>
        <Trash2 className="h-4 w-4" />
      </Button>
    </div>
  );
}
