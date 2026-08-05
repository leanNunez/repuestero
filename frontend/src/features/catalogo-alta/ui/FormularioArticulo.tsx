import { useState } from "react";

import type { ArticuloAltaRequest, ListaPrecio } from "@/entities/articulo/schema";
import { Button } from "@/shared/ui/button";
import { CampoMoneda } from "@/shared/ui/campo-moneda";
import { Card } from "@/shared/ui/card";
import { Field, FieldDescription, FieldError, FieldLabel } from "@/shared/ui/field";
import { Input } from "@/shared/ui/input";
import { NativeSelect } from "@/shared/ui/native-select";
import { WarningList } from "@/shared/ui/warning-list";

import {
  ALICUOTAS_IVA,
  aPayload,
  precioSinLista,
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
  /** Avisos no bloqueantes del alta (el más frecuente: se creó sin precio de venta). */
  advertencias: readonly string[];
  /** Rubros y marcas que YA existen, para sugerir sin obligar. */
  rubros: readonly string[];
  marcas: readonly string[];
  /** Listas de precio de la org. Puede venir vacía: no hay alta de listas por la app. */
  listas: readonly ListaPrecio[];
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
 * Lo obligatorio va en la primera fila; el resto —lo que se completa cuando se tiene a mano— en el
 * segundo bloque. */
export function FormularioArticulo({
  cargando,
  error,
  errorCodigo,
  ultimoCodigo,
  advertencias,
  rubros,
  marcas,
  listas,
  onCrear,
}: Props) {
  const [abierto, setAbierto] = useState(false);
  const [datos, setDatos] = useState<Datos>(VACIO);

  const habilitado = puedeGuardar(datos) && !cargando;
  const sinListas = listas.length === 0;
  const faltaLista = precioSinLista(datos);

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
        {ultimoCodigo && <Confirmacion codigo={ultimoCodigo} avisos={advertencias} />}
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

        {/* Segundo bloque: lo que se completa si se tiene a mano. Separado del primero a propósito
            —quien carga veinte repuestos seguidos llena los cuatro de arriba y nada más—. */}
        <div className="grid gap-3 border-t pt-3 sm:grid-cols-2 lg:grid-cols-6">
          <Sugerido
            id="art-marca"
            label="Marca"
            valor={datos.marca}
            opciones={marcas}
            placeholder="Mann-Filter"
            onChange={(v) => campo("marca", v)}
          />
          <Sugerido
            id="art-rubro"
            label="Rubro"
            valor={datos.rubro}
            opciones={rubros}
            placeholder="FILTROS"
            onChange={(v) => campo("rubro", v)}
          />

          <Field className="gap-1.5">
            <FieldLabel htmlFor="art-codigo-barra">Código de barra</FieldLabel>
            <Input
              id="art-codigo-barra"
              value={datos.codigo_barra}
              onChange={(e) => campo("codigo_barra", e.target.value)}
              placeholder="7790001234567"
              inputMode="numeric"
            />
          </Field>

          <Field className="gap-1.5">
            <FieldLabel htmlFor="art-costo-dolar">Costo en dólares</FieldLabel>
            <CampoMoneda
              id="art-costo-dolar"
              value={datos.costo_dolar}
              onChange={(v) => campo("costo_dolar", v)}
              placeholder="0,00"
              disabled={cargando}
            />
          </Field>

          <Field className="gap-1.5">
            <FieldLabel htmlFor="art-punto-pedido">Punto de pedido</FieldLabel>
            <CampoMoneda
              id="art-punto-pedido"
              value={datos.punto_pedido}
              onChange={(v) => campo("punto_pedido", v)}
              placeholder="0,00"
              disabled={cargando}
            />
          </Field>
        </div>

        {/* El precio NO es un campo del artículo: vive en `articulo_precios`, por lista. Va en su
            propio bloque para que se lea como lo que es — una decisión aparte de cargar el
            producto—, y porque sin lista elegida no se puede fijar. */}
        <div className="grid gap-3 border-t pt-3 sm:grid-cols-2 lg:grid-cols-6">
          <Field className="gap-1.5">
            <FieldLabel htmlFor="art-precio">Precio de venta</FieldLabel>
            <CampoMoneda
              id="art-precio"
              value={datos.precio}
              onChange={(v) => campo("precio", v)}
              placeholder="0,00"
              disabled={cargando || sinListas}
              aria-describedby={sinListas ? "art-precio-hint" : undefined}
            />
            {sinListas && (
              <FieldDescription id="art-precio-hint" className="text-xs">
                Esta organización no tiene listas de precio cargadas. El artículo se crea igual y el
                precio se pone después.
              </FieldDescription>
            )}
          </Field>

          <Field className="gap-1.5 lg:col-span-2" data-invalid={faltaLista || undefined}>
            <FieldLabel htmlFor="art-lista">Lista de precios</FieldLabel>
            <NativeSelect
              id="art-lista"
              value={datos.lista_id}
              onChange={(e) => campo("lista_id", e.target.value)}
              disabled={cargando || sinListas}
              aria-invalid={faltaLista}
              aria-describedby={faltaLista ? "art-lista-error" : undefined}
            >
              <option value="">Elegí una lista</option>
              {listas.map((l) => (
                <option key={l.id} value={String(l.id)}>
                  {l.nombre} ({l.codigo})
                </option>
              ))}
            </NativeSelect>
            {faltaLista && (
              <FieldError id="art-lista-error" className="text-xs">
                Elegí en qué lista va ese precio. No hay una por defecto.
              </FieldError>
            )}
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

      {ultimoCodigo && <Confirmacion codigo={ultimoCodigo} avisos={advertencias} />}
    </Card>
  );
}

/** Campo de texto libre que SUGIERE los valores que ya existen sin obligar a elegirlos.
 *
 * `<datalist>` nativo y no `Combobox`: ese componente está hecho para elegir una entidad que
 * existe —su rama de `elegido` vuelve el input de solo lectura— y lo usan ventas y compras, que
 * son pantallas de plata ya verificadas. Un modo "creatable" ahí es superficie de regresión
 * pagada por un campo donde el browser hace el trabajo gratis.
 *
 * `autoComplete="off"` no es higiene: sin eso el historial del browser compite por el mismo popup
 * y tapa las sugerencias reales. */
function Sugerido({
  id,
  label,
  valor,
  opciones,
  placeholder,
  onChange,
}: {
  id: string;
  label: string;
  valor: string;
  opciones: readonly string[];
  placeholder: string;
  onChange: (v: string) => void;
}) {
  return (
    <Field className="gap-1.5">
      <FieldLabel htmlFor={id}>{label}</FieldLabel>
      <Input
        id={id}
        value={valor}
        onChange={(e) => onChange(e.target.value)}
        list={`${id}-opciones`}
        autoComplete="off"
        placeholder={placeholder}
        aria-describedby={`${id}-hint`}
      />
      {/* Lo que importa que se anuncie es la AFFORDANCE, no el listado: los lectores de pantalla
          leen el datalist de forma inconsistente, pero "o escribí uno nuevo" siempre se escucha. */}
      <FieldDescription id={`${id}-hint`} className="text-xs">
        Elegí uno o escribí uno nuevo.
      </FieldDescription>
      <datalist id={`${id}-opciones`}>
        {opciones.map((o) => (
          <option key={o} value={o} />
        ))}
      </datalist>
    </Field>
  );
}

/** El código no lo eligió el sistema, pero sí es lo que prueba que el artículo quedó guardado con
 *  el número que la persona quería. Las advertencias van pegadas: la más frecuente es "se creó sin
 *  precio de venta", que sin el aviso se descubre recién al querer venderlo. */
function Confirmacion({ codigo, avisos }: { codigo: string; avisos: readonly string[] }) {
  return (
    <div className="space-y-2">
      <p role="status" className="text-sm text-muted-foreground">
        Artículo dado de alta con el código <strong className="text-foreground">{codigo}</strong>.
      </p>
      <WarningList avisos={avisos} />
    </div>
  );
}
