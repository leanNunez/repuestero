import { useState } from "react";

import type { ArticuloAltaRequest } from "@/entities/articulo/schema";
import { Button } from "@/shared/ui/button";
import { CampoMoneda } from "@/shared/ui/campo-moneda";
import { Card } from "@/shared/ui/card";
import { Field, FieldError, FieldLabel } from "@/shared/ui/field";
import { Input } from "@/shared/ui/input";
import { NativeSelect } from "@/shared/ui/native-select";

import {
  ALICUOTAS_IVA,
  aPayload,
  puedeGuardar,
  VACIO,
  type AlicuotaIva,
  type FormularioArticulo as Datos,
} from "../model/estado";

interface Props {
  cargando: boolean;
  /** Error general del alta (todo lo que no sea el código repetido). */
  error: string | null;
  /** El 409 por código duplicado, que se ancla al campo `codigo` y no al pie del formulario. */
  errorCodigo: string | null;
  /** Código del último artículo dado de alta. Lo tipeó la persona, así que no es una revelación
   *  como en clientes — pero es la prueba de que el alta ocurrió. */
  ultimoCodigo: string | null;
  /** Devuelve una promesa: el formulario necesita saber si el alta salió bien para recién ahí
   *  limpiarse. Ver el comentario de `enviar`. */
  onCrear: (v: ArticuloAltaRequest) => Promise<unknown>;
}

/** Alta de artículo.
 *
 * A diferencia de clientes, acá el código lo TIPEA la persona: es el del fabricante (`MAH-OC90`),
 * que es como el cliente lo pide en el mostrador y como viene impreso en la caja. El sistema no
 * tiene nada mejor que inventar.
 *
 * Este formulario pide solo lo obligatorio. Marca, rubro, precio y los demás opcionales llegan en
 * el paso siguiente. */
export function FormularioArticulo({
  cargando,
  error,
  errorCodigo,
  ultimoCodigo,
  onCrear,
}: Props) {
  const [abierto, setAbierto] = useState(false);
  const [datos, setDatos] = useState<Datos>(VACIO);

  const habilitado = puedeGuardar(datos) && !cargando;

  function campo<K extends keyof Datos>(k: K, v: Datos[K]) {
    setDatos((d) => ({ ...d, [k]: v }));
  }

  /** El formulario se limpia en el ÉXITO, no en el submit.
   *
   * Clientes se limpia optimistamente porque su alta casi no puede fallar: el código lo genera el
   * servidor. Acá el código lo tipea la persona y el 409 por duplicado es un resultado ESPERABLE
   * —el que carga repuestos todo el día se cruza con uno ya cargado seguido—. Limpiar en el submit
   * le borraría todo lo escrito justo cuando necesita corregir un campo. */
  async function enviar(e: React.FormEvent) {
    e.preventDefault();
    if (!habilitado) return;

    try {
      await onCrear(aPayload(datos));
      setDatos(VACIO);
    } catch {
      /* El error ya se muestra; lo tipeado queda en pantalla para corregirlo. */
    }
  }

  if (!abierto) {
    return (
      <div className="space-y-2">
        <Button size="sm" onClick={() => setAbierto(true)}>
          Nuevo artículo
        </Button>
        {ultimoCodigo && <Confirmacion codigo={ultimoCodigo} />}
      </div>
    );
  }

  return (
    <Card className="space-y-3 p-3">
      <form onSubmit={(e) => void enviar(e)} className="space-y-3">
        {/* 6 columnas y no 4: con 4, el detalle ocupando dos deja al IVA solo en una segunda fila y
            el formulario se lee como si le faltara algo. Los cuatro campos entran en una fila. */}
        <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-6">
          <Field className="gap-1.5" data-invalid={errorCodigo ? true : undefined}>
            <FieldLabel htmlFor="art-codigo">Código</FieldLabel>
            <Input
              id="art-codigo"
              value={datos.codigo}
              onChange={(e) => campo("codigo", e.target.value)}
              maxLength={40}
              placeholder="MAH-OC90"
              aria-invalid={errorCodigo !== null}
              aria-describedby={errorCodigo ? "art-codigo-error" : undefined}
            />
            {errorCodigo && (
              <FieldError id="art-codigo-error" className="text-xs">
                {errorCodigo}
              </FieldError>
            )}
          </Field>

          <Field className="gap-1.5 sm:col-span-1 lg:col-span-3">
            <FieldLabel htmlFor="art-detalle">Detalle</FieldLabel>
            <Input
              id="art-detalle"
              value={datos.detalle}
              onChange={(e) => campo("detalle", e.target.value)}
              maxLength={200}
              placeholder="Filtro de aceite Gol 1.6"
            />
          </Field>

          <Field className="gap-1.5">
            <FieldLabel htmlFor="art-costo">Costo</FieldLabel>
            <CampoMoneda
              id="art-costo"
              value={datos.costo}
              onChange={(v) => campo("costo", v)}
              placeholder="0,00"
              disabled={cargando}
            />
          </Field>

          <Field className="gap-1.5">
            <FieldLabel htmlFor="art-iva">IVA</FieldLabel>
            <NativeSelect
              id="art-iva"
              value={datos.alicuota_iva}
              onChange={(e) => campo("alicuota_iva", e.target.value as AlicuotaIva)}
            >
              {ALICUOTAS_IVA.map((a) => (
                <option key={a.id} value={a.id}>
                  {a.label}
                </option>
              ))}
            </NativeSelect>
          </Field>
        </div>

        {error && <FieldError>{error}</FieldError>}

        <div className="flex gap-2">
          <Button type="submit" size="sm" disabled={!habilitado}>
            {cargando ? "Guardando…" : "Dar de alta"}
          </Button>
          <Button type="button" variant="ghost" size="sm" onClick={() => setAbierto(false)}>
            Cerrar
          </Button>
        </div>
      </form>

      {ultimoCodigo && <Confirmacion codigo={ultimoCodigo} />}
    </Card>
  );
}

/** El código no lo eligió el sistema, pero sí es lo que prueba que el artículo quedó guardado con
 *  el número que la persona quería. */
function Confirmacion({ codigo }: { codigo: string }) {
  return (
    <p role="status" className="text-sm text-muted-foreground">
      Artículo dado de alta con el código <strong className="text-foreground">{codigo}</strong>.
    </p>
  );
}
