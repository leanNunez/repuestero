import { AlertTriangle, Loader2, PackageCheck } from "lucide-react";

import type { ConfirmarResponse } from "@/entities/remito/schema";
import { Button } from "@/shared/ui/button";
import { Card } from "@/shared/ui/card";

import { flagsDeAtencion, MAX_CODIGO_PROVEEDOR, type Estado } from "../model/estado";

const inputClass =
  "h-9 w-full rounded-md border border-input bg-background px-3 text-sm focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring";

interface Props {
  estado: Estado;
  onCampo: (campo: "deposito" | "proveedorCodigo" | "numeroRemito", valor: string) => void;
  onConfirmar: () => void;
  puede: boolean;
  cargando: boolean;
  error?: string | null;
}

export function ResumenConfirmar({
  estado,
  onCampo,
  onConfirmar,
  puede,
  cargando,
  error,
}: Props) {
  const incluidos = estado.renglones.filter((r) => r.incluir);
  const altas = incluidos.filter((r) => r.accion === "alta").length;
  const marcados = incluidos.filter((r) => flagsDeAtencion(r).length > 0).length;

  return (
    <Card className="space-y-4 p-4">
      <div className="grid gap-3 sm:grid-cols-3">
        <div className="space-y-1">
          <label htmlFor="deposito" className="text-xs font-medium">
            Depósito <span className="text-destructive">*</span>
          </label>
          <input
            id="deposito"
            value={estado.deposito}
            onChange={(e) => onCampo("deposito", e.target.value)}
            placeholder="CEN"
            className={inputClass}
          />
          <p className="text-[11px] text-muted-foreground">A dónde entra la mercadería.</p>
        </div>

        <div className="space-y-1">
          <label htmlFor="proveedor" className="text-xs font-medium">
            Código de proveedor
          </label>
          <input
            id="proveedor"
            value={estado.proveedorCodigo}
            onChange={(e) => onCampo("proveedorCodigo", e.target.value)}
            placeholder="DIST-SUR"
            maxLength={MAX_CODIGO_PROVEEDOR}
            className={inputClass}
          />
          <p className="text-[11px] text-muted-foreground">
            Código corto interno (opcional).{" "}
            {estado.propuesta?.proveedor_nombre
              ? `El proveedor «${estado.propuesta.proveedor_nombre}» se guarda solo.`
              : ""}
          </p>
        </div>

        <div className="space-y-1">
          <label htmlFor="numero" className="text-xs font-medium">
            N° de remito
          </label>
          <input
            id="numero"
            value={estado.numeroRemito}
            onChange={(e) => onCampo("numeroRemito", e.target.value)}
            placeholder="R-0001"
            className={inputClass}
          />
          <p className="text-[11px] text-muted-foreground">Evita cargarlo dos veces.</p>
        </div>
      </div>

      <div className="flex flex-wrap items-center justify-between gap-3 border-t pt-3">
        <div className="text-sm">
          <p className="font-medium">
            {incluidos.length} de {estado.renglones.length} renglones
          </p>
          <p className="text-xs text-muted-foreground">
            {altas > 0 && `${altas} artículo(s) nuevos · `}
            {marcados > 0 ? `${marcados} necesitan tu atención` : "ninguno marcado"}
          </p>
        </div>

        <Button onClick={onConfirmar} disabled={!puede || cargando}>
          {cargando ? (
            <>
              <Loader2 className="h-4 w-4 animate-spin" />
              Cargando…
            </>
          ) : (
            <>
              <PackageCheck className="h-4 w-4" />
              Confirmar y cargar
            </>
          )}
        </Button>
      </div>

      {!puede && !cargando && (
        <p className="flex items-center gap-1.5 text-xs text-muted-foreground">
          <AlertTriangle className="h-3.5 w-3.5" />
          {estado.deposito.trim().length === 0
            ? "Indicá el depósito para poder cargar."
            : incluidos.length === 0
              ? "Tildá al menos un renglón."
              : "Hay renglones incluidos con datos incompletos."}
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

export function ResultadoCarga({
  resultado,
  onOtro,
}: {
  resultado: ConfirmarResponse;
  onOtro: () => void;
}) {
  return (
    <div className="mx-auto flex max-w-lg flex-col items-center gap-4 py-10 text-center">
      <div className="flex h-16 w-16 items-center justify-center rounded-2xl bg-emerald-100 text-emerald-700 dark:bg-emerald-950 dark:text-emerald-400">
        <PackageCheck className="h-8 w-8" />
      </div>

      <div>
        <h2 className="text-lg font-semibold">Remito cargado</h2>
        <p className="mt-1 text-sm text-muted-foreground">
          {resultado.articulos_creados.length} artículo(s) nuevos ·{" "}
          {resultado.articulos_actualizados.length} actualizados ·{" "}
          {resultado.movimientos} movimiento(s) de stock ·{" "}
          {resultado.precios_recalculados} precio(s) recalculados
        </p>
      </div>

      {resultado.advertencias.length > 0 && (
        <ul className="w-full space-y-1.5 rounded-lg bg-amber-50 p-3 text-left text-sm text-amber-900 dark:bg-amber-950/40 dark:text-amber-200">
          {resultado.advertencias.map((a) => (
            <li key={a} className="flex gap-2">
              <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0" />
              {a}
            </li>
          ))}
        </ul>
      )}

      <Button variant="outline" onClick={onOtro}>
        Cargar otro remito
      </Button>
    </div>
  );
}
