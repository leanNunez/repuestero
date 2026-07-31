import { AlertTriangle, Loader2, PackageCheck } from "lucide-react";

import type { ConfirmarResponse } from "@/entities/remito/schema";
import { Button } from "@/shared/ui/button";
import { Card } from "@/shared/ui/card";
import { Field, FieldDescription, FieldLabel } from "@/shared/ui/field";
import { Input } from "@/shared/ui/input";
import { SuccessPanel } from "@/shared/ui/success-panel";
import { WarningList } from "@/shared/ui/warning-list";

import { flagsDeAtencion, MAX_CODIGO_PROVEEDOR, type Estado } from "../model/estado";

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
        <Field className="gap-1.5">
          <FieldLabel htmlFor="deposito" className="text-xs">
            Depósito <span className="text-destructive">*</span>
          </FieldLabel>
          <Input
            id="deposito"
            value={estado.deposito}
            onChange={(e) => onCampo("deposito", e.target.value)}
            placeholder="CEN"
          />
          <FieldDescription className="text-[11px]">
            A dónde entra la mercadería.
          </FieldDescription>
        </Field>

        <Field className="gap-1.5">
          <FieldLabel htmlFor="proveedor" className="text-xs">
            Código de proveedor
          </FieldLabel>
          <Input
            id="proveedor"
            value={estado.proveedorCodigo}
            onChange={(e) => onCampo("proveedorCodigo", e.target.value)}
            placeholder="DIST-SUR"
            maxLength={MAX_CODIGO_PROVEEDOR}
          />
          <FieldDescription className="text-[11px]">
            Código corto interno (opcional).{" "}
            {estado.propuesta?.proveedor_nombre
              ? `El proveedor «${estado.propuesta.proveedor_nombre}» se guarda solo.`
              : ""}
          </FieldDescription>
        </Field>

        <Field className="gap-1.5">
          <FieldLabel htmlFor="numero" className="text-xs">
            N° de remito
          </FieldLabel>
          <Input
            id="numero"
            value={estado.numeroRemito}
            onChange={(e) => onCampo("numeroRemito", e.target.value)}
            placeholder="R-0001"
          />
          <FieldDescription className="text-[11px]">Evita cargarlo dos veces.</FieldDescription>
        </Field>
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
    <SuccessPanel className="mx-auto max-w-lg py-10" icon={<PackageCheck className="h-8 w-8" />}>
      <div>
        <h1 className="text-lg font-semibold">Remito cargado</h1>
        <p className="mt-1 text-sm text-muted-foreground">
          {resultado.articulos_creados.length} artículo(s) nuevos ·{" "}
          {resultado.articulos_actualizados.length} actualizados ·{" "}
          {resultado.movimientos} movimiento(s) de stock ·{" "}
          {resultado.precios_recalculados} precio(s) recalculados
        </p>
      </div>

      <WarningList avisos={resultado.advertencias} className="w-full" />

      <Button variant="outline" onClick={onOtro}>
        Cargar otro remito
      </Button>
    </SuccessPanel>
  );
}
