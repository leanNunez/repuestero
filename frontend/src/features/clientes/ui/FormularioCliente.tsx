import { useState } from "react";

import type { ClienteCrear } from "@/entities/cliente/schema";
import { Button } from "@/shared/ui/button";
import { CampoMoneda } from "@/shared/ui/campo-moneda";
import { Card } from "@/shared/ui/card";

import {
  aPayload,
  CONDICIONES_FISCALES,
  cuitAceptable,
  puedeGuardar,
  VACIO,
  type CondFiscal,
  type FormularioCliente as Datos,
} from "../model/estado";

const campoClass =
  "h-9 w-full rounded-md border border-input bg-background px-3 text-sm focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 focus-visible:ring-offset-background";

interface Props {
  cargando: boolean;
  error: string | null;
  /** Código del último cliente dado de alta (`CLI-000001`). El servidor lo asigna, así que es lo
   *  único que confirma que el alta ocurrió de verdad. */
  ultimoCodigo: string | null;
  onCrear: (v: ClienteCrear) => void;
}

/** Alta de cliente.
 *
 * NO se pide el código: lo genera el servidor. Mostrar un campo vacío y deshabilitado sería peor
 * que no mostrarlo — invita a preguntarse qué va ahí. El número aparece recién cuando existe, en
 * el aviso de confirmación y en la tabla.
 *
 * Lo único obligatorio es la denominación. Un consumidor final que compra una vez no tiene por qué
 * dar CUIT, teléfono ni dirección, y exigírselo al de la caja significa que va a inventar algo. */
export function FormularioCliente({ cargando, error, ultimoCodigo, onCrear }: Props) {
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
          Nuevo cliente
        </Button>
        {ultimoCodigo && <Confirmacion codigo={ultimoCodigo} />}
      </div>
    );
  }

  return (
    <Card className="space-y-3 p-3">
      <form onSubmit={enviar} className="space-y-3">
        <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
          <div className="space-y-1 sm:col-span-2">
            <label htmlFor="cli-denominacion" className="text-xs text-muted-foreground">
              Nombre o razón social
            </label>
            <input
              id="cli-denominacion"
              value={datos.denominacion}
              onChange={(e) => campo("denominacion", e.target.value)}
              maxLength={140}
              placeholder="Taller Mecánico El Rulo"
              className={campoClass}
            />
          </div>

          <div className="space-y-1">
            <label htmlFor="cli-cond-fiscal" className="text-xs text-muted-foreground">
              Condición fiscal
            </label>
            <select
              id="cli-cond-fiscal"
              value={datos.cond_fiscal}
              onChange={(e) => campo("cond_fiscal", e.target.value as CondFiscal)}
              className={campoClass}
            >
              {CONDICIONES_FISCALES.map((c) => (
                <option key={c.id} value={c.id}>
                  {c.label}
                </option>
              ))}
            </select>
          </div>

          <div className="space-y-1">
            <label htmlFor="cli-cuit" className="text-xs text-muted-foreground">
              CUIT (opcional)
            </label>
            <input
              id="cli-cuit"
              value={datos.cuit}
              onChange={(e) => campo("cuit", e.target.value)}
              maxLength={13}
              placeholder="30-71233445-9"
              aria-invalid={cuitMal}
              aria-describedby={cuitMal ? "cli-cuit-error" : undefined}
              className={campoClass}
            />
            {cuitMal && (
              <p id="cli-cuit-error" role="alert" className="text-xs text-destructive">
                Ese CUIT no es válido. Revisá el número — no coincide el dígito verificador.
              </p>
            )}
          </div>

          <div className="space-y-1">
            <label htmlFor="cli-limite" className="text-xs text-muted-foreground">
              Límite de cuenta corriente
            </label>
            <CampoMoneda
              id="cli-limite"
              value={datos.limite_cta_cte}
              onChange={(v) => campo("limite_cta_cte", v)}
              placeholder="0,00"
              disabled={cargando}
              className={campoClass}
            />
          </div>

          <div className="space-y-1">
            <label htmlFor="cli-telefono" className="text-xs text-muted-foreground">
              Teléfono (opcional)
            </label>
            <input
              id="cli-telefono"
              value={datos.telefono}
              onChange={(e) => campo("telefono", e.target.value)}
              maxLength={40}
              placeholder="0341-155667788"
              className={campoClass}
            />
          </div>

          <div className="space-y-1">
            <label htmlFor="cli-email" className="text-xs text-muted-foreground">
              Email (opcional)
            </label>
            <input
              id="cli-email"
              type="email"
              value={datos.email}
              onChange={(e) => campo("email", e.target.value)}
              maxLength={120}
              placeholder="taller@gmail.com"
              className={campoClass}
            />
          </div>

          {/* Ocupa las columnas que le quedan al email para que la grilla cierre: si va sola en su
              fila, el formulario se lee como si le faltara algo. */}
          <div className="space-y-1 lg:col-span-2">
            <label htmlFor="cli-direccion" className="text-xs text-muted-foreground">
              Dirección (opcional)
            </label>
            <input
              id="cli-direccion"
              value={datos.direccion}
              onChange={(e) => campo("direccion", e.target.value)}
              maxLength={160}
              placeholder="Av. San Martín 2340, Rosario"
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
      Cliente dado de alta con el código <strong className="text-foreground">{codigo}</strong>.
    </p>
  );
}
