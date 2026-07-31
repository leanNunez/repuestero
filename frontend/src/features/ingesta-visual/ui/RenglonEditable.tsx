import { ArrowRight, Sparkles } from "lucide-react";

import { pesos } from "@/entities/remito/formato";
import { FLAG_TEXTO, type Flag, type PrecioPreview } from "@/entities/remito/schema";
import { cn } from "@/shared/lib/cn";
import { Badge } from "@/shared/ui/badge";
import { Input } from "@/shared/ui/input";

import {
  flagsDeAtencion,
  renglonValido,
  type RenglonEditable as Renglon,
} from "../model/estado";

function PrecioFila({ p }: { p: PrecioPreview }) {
  // Sin margen no hay precio nuevo: la regla es que NO se inventa uno.
  if (p.precio_nuevo === null) {
    return (
      <div className="flex items-center gap-1.5 text-xs">
        <span className="text-muted-foreground">{p.lista_nombre}:</span>
        <span className="font-mono font-medium tabular-nums">{pesos(p.precio_actual)}</span>
        <span className="text-warning">— sin margen, no se toca</span>
      </div>
    );
  }

  return (
    <div className="flex items-center gap-1.5 text-xs">
      <span className="text-muted-foreground">{p.lista_nombre}:</span>
      <span className="font-mono tabular-nums text-muted-foreground line-through">
        {pesos(p.precio_actual)}
      </span>
      <ArrowRight className="h-3 w-3 text-muted-foreground" />
      <span className="font-mono font-semibold tabular-nums text-success">
        {pesos(p.precio_nuevo)}
      </span>
      <span className="text-muted-foreground">({p.margen}%)</span>
    </div>
  );
}

interface Props {
  renglon: Renglon;
  onCampo: (campo: keyof Renglon, valor: string | boolean) => void;
}

export function RenglonEditableRow({ renglon: r, onCampo }: Props) {
  const invalido = r.incluir && !renglonValido(r);
  const atencion = flagsDeAtencion(r);

  return (
    <div
      className={cn(
        "grid grid-cols-[auto_1fr] gap-3 border-b p-3 last:border-b-0",
        atencion.length > 0 && "bg-warning/5",
        !r.incluir && "opacity-55",
        invalido && "bg-destructive/5",
      )}
    >
      <input
        type="checkbox"
        checked={r.incluir}
        onChange={(e) => onCampo("incluir", e.target.checked)}
        aria-label={`Incluir ${r.codigo_editado || r.detalle_editado}`}
        className="mt-1.5 h-4 w-4 shrink-0 rounded border-input accent-primary"
      />

      <div className="min-w-0 space-y-2">
        <div className="flex flex-wrap items-center gap-1.5">
          <Badge
            className={cn(
              "px-1.5 py-0 text-[10px]",
              // El alta se destaca con el acento de marca; la actualización queda neutra.
              r.accion === "alta" && "bg-accent text-accent-foreground",
            )}
          >
            {r.accion === "alta" ? "Artículo nuevo" : "Ya existe"}
          </Badge>

          {/* `alta_sin_precio` ya quedó afuera (ver flagsDeAtencion): el badge "Artículo
              nuevo" y la línea de abajo lo dicen. Tres veces el mismo aviso no avisa más. */}
          {atencion.map((f) => (
            <Badge
              key={f}
              variant="warning"
              title={FLAG_TEXTO[f as Flag].detalle}
              className="px-1.5 py-0 text-[10px]"
            >
              {FLAG_TEXTO[f as Flag].label}
            </Badge>
          ))}

          {r.confianza < 1 && (
            <span className="ml-auto flex items-center gap-1 text-[10px] text-muted-foreground">
              <Sparkles className="h-3 w-3" />
              {Math.round(r.confianza * 100)}%
            </span>
          )}
        </div>

        <div className="grid gap-2 sm:grid-cols-[140px_1fr_80px_120px]">
          <label className="sr-only" htmlFor={`cod-${r.codigo ?? r.descripcion}`}>
            Código
          </label>
          <Input
            id={`cod-${r.codigo ?? r.descripcion}`}
            value={r.codigo_editado}
            onChange={(e) => onCampo("codigo_editado", e.target.value)}
            placeholder="Código"
            aria-invalid={!r.codigo_editado.trim()}
            className="h-8 font-mono"
          />
          <Input
            value={r.detalle_editado}
            onChange={(e) => onCampo("detalle_editado", e.target.value)}
            placeholder="Descripción"
            aria-label="Descripción"
            className="h-8"
          />
          <Input
            value={r.cantidad_editada}
            onChange={(e) => onCampo("cantidad_editada", e.target.value)}
            inputMode="decimal"
            placeholder="Cant."
            aria-label="Cantidad"
            className="h-8 text-right font-mono tabular-nums"
          />
          <Input
            value={r.costo_editado}
            onChange={(e) => onCampo("costo_editado", e.target.value)}
            inputMode="decimal"
            placeholder="Costo"
            aria-label="Costo unitario"
            className="h-8 text-right font-mono tabular-nums"
          />
        </div>

        {/* Lo que ya sabe el sistema: el contexto que convierte "aceptar" en una decisión. */}
        {r.accion === "actualizacion" && (
          <p className="text-xs text-muted-foreground">
            Hoy: <span className="font-medium">{r.detalle_actual}</span> · costo{" "}
            <span className="font-mono font-medium tabular-nums">
              {pesos(r.costo_actual ?? "0")}
            </span>
          </p>
        )}

        {r.precios.length > 0 && (
          <div className="space-y-0.5 rounded-md bg-background/60 p-2">
            {r.precios.map((p) => (
              <PrecioFila key={p.lista_codigo} p={p} />
            ))}
          </div>
        )}

        {r.accion === "alta" && (
          <p className="text-xs text-primary">
            Se crea sin precio de venta — poneselo desde el catálogo.
          </p>
        )}

        {invalido && (
          <p role="alert" className="text-xs font-medium text-destructive">
            Completá código, descripción y una cantidad mayor a cero.
          </p>
        )}
      </div>
    </div>
  );
}
