import { useState } from "react";

import type { ProveedorCrear } from "@/entities/proveedor/schema";
import { Button } from "@/shared/ui/button";
import { Card } from "@/shared/ui/card";
import { Field, FieldError, FieldLabel } from "@/shared/ui/field";
import { Input } from "@/shared/ui/input";

import {
  aPayload,
  cuitAceptable,
  puedeGuardar,
  VACIO,
  type FormularioProveedor as Datos,
} from "../model/estado";

interface Props {
  cargando: boolean;
  error: string | null;
  /** Código del último proveedor dado de alta (`PRV-000001`). El servidor lo asigna, así que es lo
   *  único que confirma que el alta ocurrió de verdad. */
  ultimoCodigo: string | null;
  onCrear: (v: ProveedorCrear) => void;
}

/** Alta de proveedor.
 *
 * NO se pide el código: lo genera el servidor. Mostrar un campo vacío y deshabilitado sería peor
 * que no mostrarlo — invita a preguntarse qué va ahí.
 *
 * Lo único obligatorio es la razón social. A un proveedor nuevo muchas veces se lo carga con el
 * nombre que figura en el remito y nada más; el resto se completa cuando se sabe. */
export function FormularioProveedor({ cargando, error, ultimoCodigo, onCrear }: Props) {
  const [abierto, setAbierto] = useState(false);
  const [datos, setDatos] = useState<Datos>(VACIO);

  const cuitMal = datos.cuit.trim() !== "" && !cuitAceptable(datos.cuit);
  const habilitado = puedeGuardar(datos) && !cargando;

  function campo<K extends keyof Datos>(k: K, v: Datos[K]) {
    setDatos((d) => ({ ...d, [k]: v }));
  }

  function enviar(e: React.FormEvent) {
    e.preventDefault();
    if (!habilitado) return;

    onCrear(aPayload(datos));
    setDatos(VACIO);
  }

  if (!abierto) {
    return (
      <div className="space-y-2">
        <Button size="sm" onClick={() => setAbierto(true)}>
          Nuevo proveedor
        </Button>
        {ultimoCodigo && <Confirmacion codigo={ultimoCodigo} />}
      </div>
    );
  }

  return (
    <Card className="space-y-3 p-3">
      <form onSubmit={enviar} className="space-y-3">
        <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
          <Field className="gap-1.5 lg:col-span-2">
            <FieldLabel htmlFor="prv-razon-social">Razón social</FieldLabel>
            <Input
              id="prv-razon-social"
              value={datos.razon_social}
              onChange={(e) => campo("razon_social", e.target.value)}
              maxLength={120}
              placeholder="Distribuidora Central SA"
            />
          </Field>

          <Field className="gap-1.5" data-invalid={cuitMal || undefined}>
            <FieldLabel htmlFor="prv-cuit">CUIT (opcional)</FieldLabel>
            <Input
              id="prv-cuit"
              value={datos.cuit}
              onChange={(e) => campo("cuit", e.target.value)}
              maxLength={13}
              placeholder="30-71233445-9"
              aria-invalid={cuitMal}
              aria-describedby={cuitMal ? "prv-cuit-error" : undefined}
            />
            {cuitMal && (
              <FieldError id="prv-cuit-error" className="text-xs">
                Ese CUIT no es válido. Revisá el número — no coincide el dígito verificador.
              </FieldError>
            )}
          </Field>

          <Field className="gap-1.5">
            <FieldLabel htmlFor="prv-telefono">Teléfono (opcional)</FieldLabel>
            <Input
              id="prv-telefono"
              value={datos.telefono}
              onChange={(e) => campo("telefono", e.target.value)}
              maxLength={40}
              placeholder="0341-4567890"
            />
          </Field>

          <Field className="gap-1.5 lg:col-span-2">
            <FieldLabel htmlFor="prv-email">Email (opcional)</FieldLabel>
            <Input
              id="prv-email"
              type="email"
              value={datos.email}
              onChange={(e) => campo("email", e.target.value)}
              maxLength={120}
              placeholder="ventas@distribuidora.com"
            />
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

/** El código es lo único que la persona no eligió, así que es lo que necesita ver para saber que el
 *  alta salió y con qué número quedó. */
function Confirmacion({ codigo }: { codigo: string }) {
  return (
    <p role="status" className="text-sm text-muted-foreground">
      Proveedor dado de alta con el código <strong className="text-foreground">{codigo}</strong>.
    </p>
  );
}
