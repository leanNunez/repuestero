import { useState } from "react";

import type { ProveedorCrear } from "@/entities/proveedor/schema";
import { Button } from "@/shared/ui/button";
import { Card } from "@/shared/ui/card";

import {
  aPayload,
  cuitAceptable,
  puedeGuardar,
  VACIO,
  type FormularioProveedor as Datos,
} from "../model/estado";

const campoClass =
  "h-9 w-full rounded-md border border-input bg-background px-3 text-sm focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 focus-visible:ring-offset-background";

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
          <div className="space-y-1 lg:col-span-2">
            <label htmlFor="prv-razon-social" className="text-xs text-muted-foreground">
              Razón social
            </label>
            <input
              id="prv-razon-social"
              value={datos.razon_social}
              onChange={(e) => campo("razon_social", e.target.value)}
              maxLength={120}
              placeholder="Distribuidora Central SA"
              className={campoClass}
            />
          </div>

          <div className="space-y-1">
            <label htmlFor="prv-cuit" className="text-xs text-muted-foreground">
              CUIT (opcional)
            </label>
            <input
              id="prv-cuit"
              value={datos.cuit}
              onChange={(e) => campo("cuit", e.target.value)}
              maxLength={13}
              placeholder="30-71233445-9"
              aria-invalid={cuitMal}
              aria-describedby={cuitMal ? "prv-cuit-error" : undefined}
              className={campoClass}
            />
            {cuitMal && (
              <p id="prv-cuit-error" role="alert" className="text-xs text-destructive">
                Ese CUIT no es válido. Revisá el número — no coincide el dígito verificador.
              </p>
            )}
          </div>

          <div className="space-y-1">
            <label htmlFor="prv-telefono" className="text-xs text-muted-foreground">
              Teléfono (opcional)
            </label>
            <input
              id="prv-telefono"
              value={datos.telefono}
              onChange={(e) => campo("telefono", e.target.value)}
              maxLength={40}
              placeholder="0341-4567890"
              className={campoClass}
            />
          </div>

          <div className="space-y-1 lg:col-span-2">
            <label htmlFor="prv-email" className="text-xs text-muted-foreground">
              Email (opcional)
            </label>
            <input
              id="prv-email"
              type="email"
              value={datos.email}
              onChange={(e) => campo("email", e.target.value)}
              maxLength={120}
              placeholder="ventas@distribuidora.com"
              className={campoClass}
            />
          </div>
        </div>

        {error && (
          <p role="alert" className="text-sm text-destructive">
            {error}
          </p>
        )}

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
