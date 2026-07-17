import { ArrowRight, Sparkles } from "lucide-react";

import { pesos } from "@/entities/remito/formato";
import { FLAG_TEXTO, type Flag, type PrecioPreview } from "@/entities/remito/schema";
import { cn } from "@/shared/lib/cn";
import { Badge } from "@/shared/ui/badge";

import {
  flagsDeAtencion,
  renglonValido,
  type RenglonEditable as Renglon,
} from "../model/estado";

const inputClass =
  "h-8 w-full rounded-md border border-input bg-background px-2 text-sm focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring";

function PrecioFila({ p }: { p: PrecioPreview }) {
  // Sin margen no hay precio nuevo: la regla es que NO se inventa uno.
  if (p.precio_nuevo === null) {
    return (
      <div className="flex items-center gap-1.5 text-xs">
        <span className="text-muted-foreground">{p.lista_nombre}:</span>
        <span className="font-medium">{pesos(p.precio_actual)}</span>
        <span className="text-amber-600 dark:text-amber-500">— sin margen, no se toca</span>
      </div>
    );
  }

  return (
    <div className="flex items-center gap-1.5 text-xs">
      <span className="text-muted-foreground">{p.lista_nombre}:</span>
      <span className="text-muted-foreground line-through">{pesos(p.precio_actual)}</span>
      <ArrowRight className="h-3 w-3 text-muted-foreground" />
      <span className="font-semibold text-emerald-700 dark:text-emerald-400">
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
        atencion.length > 0 && "bg-amber-50/60 dark:bg-amber-950/20",
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
              r.accion === "alta"
                ? "bg-blue-100 text-blue-800 dark:bg-blue-950 dark:text-blue-300"
                : "bg-slate-100 text-slate-700 dark:bg-slate-800 dark:text-slate-300",
            )}
          >
            {r.accion === "alta" ? "Artículo nuevo" : "Ya existe"}
          </Badge>

          {/* `alta_sin_precio` ya quedó afuera (ver flagsDeAtencion): el badge "Artículo
              nuevo" y la línea de abajo lo dicen. Tres veces el mismo aviso no avisa más. */}
          {atencion.map((f) => (
            <Badge
              key={f}
              title={FLAG_TEXTO[f as Flag].detalle}
              className="bg-amber-100 px-1.5 py-0 text-[10px] text-amber-900 dark:bg-amber-900/60 dark:text-amber-200"
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
          <input
            id={`cod-${r.codigo ?? r.descripcion}`}
            value={r.codigo_editado}
            onChange={(e) => onCampo("codigo_editado", e.target.value)}
            placeholder="Código"
            className={cn(inputClass, "font-mono", !r.codigo_editado.trim() && "border-destructive")}
          />
          <input
            value={r.detalle_editado}
            onChange={(e) => onCampo("detalle_editado", e.target.value)}
            placeholder="Descripción"
            aria-label="Descripción"
            className={inputClass}
          />
          <input
            value={r.cantidad_editada}
            onChange={(e) => onCampo("cantidad_editada", e.target.value)}
            inputMode="decimal"
            placeholder="Cant."
            aria-label="Cantidad"
            className={cn(inputClass, "text-right")}
          />
          <input
            value={r.costo_editado}
            onChange={(e) => onCampo("costo_editado", e.target.value)}
            inputMode="decimal"
            placeholder="Costo"
            aria-label="Costo unitario"
            className={cn(inputClass, "text-right")}
          />
        </div>

        {/* Lo que ya sabe el sistema: el contexto que convierte "aceptar" en una decisión. */}
        {r.accion === "actualizacion" && (
          <p className="text-xs text-muted-foreground">
            Hoy: <span className="font-medium">{r.detalle_actual}</span> · costo{" "}
            <span className="font-medium">{pesos(r.costo_actual ?? "0")}</span>
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
          <p className="text-xs text-blue-700 dark:text-blue-400">
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
