import { Search, X } from "lucide-react";
import { useEffect, useRef, useState } from "react";

import type { Cliente } from "@/entities/cliente/schema";
import { useClientes } from "@/features/clientes/model/hooks";
import { moverIndice } from "@/features/ventas/model/estado";
import { Card } from "@/shared/ui/card";

const inputClass =
  "h-9 w-full rounded-md border border-input bg-background pl-10 pr-3 text-sm focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring";

/** Elige el cliente de la venta. El backend exige `cliente_codigo`, así que no hay opción vacía
 * válida: mientras no se elija uno, la venta no se puede emitir.
 *
 * Era un `<select>` con los primeros clientes por orden alfabético. Con 900 en la org eso
 * significaba que **no se le podía facturar a un cliente que no estuviera en esa tanda**: el
 * mostrador quedaba parado por una limitación de la pantalla, no del sistema.
 *
 * Ahora busca contra el servidor (denominación, código o CUIT) y muestra los que coinciden. La
 * lista nunca es el padrón entero: es el resultado de lo que se escribió.
 */
export function SelectorCliente({
  value,
  onChange,
}: {
  value: string;
  onChange: (codigo: string) => void;
}) {
  const [q, setQ] = useState("");
  const [elegido, setElegido] = useState<Cliente | null>(null);
  const [activo, setActivo] = useState(-1);
  const inputRef = useRef<HTMLInputElement>(null);

  const texto = q.trim();
  const { data, isFetching, isError } = useClientes(texto, 1);
  // Sin texto no se pide nada al servidor: una lista de clientes cualquiera no ayuda a elegir.
  const opciones = texto ? (data?.items ?? []).filter((c) => c.activo) : [];

  // El padre puede limpiar el cliente (al emitir la venta, el estado se resetea). Si eso pasa, la
  // pantalla tiene que dejar de mostrar al que estaba elegido, o miente sobre la venta en curso.
  useEffect(() => {
    if (value === "") setElegido(null);
  }, [value]);

  function elegir(c: Cliente) {
    setElegido(c);
    onChange(c.codigo);
    setQ("");
    setActivo(-1);
  }

  function limpiar() {
    setElegido(null);
    onChange("");
    setQ("");
    setActivo(-1);
    inputRef.current?.focus();
  }

  function onKeyDown(e: React.KeyboardEvent<HTMLInputElement>) {
    if (e.key === "ArrowDown" || e.key === "ArrowUp") {
      // Prevenir el default: sin esto la flecha mueve el cursor dentro del texto y la lista y el
      // cursor pelean por la misma tecla.
      e.preventDefault();
      setActivo((i) => moverIndice(i, e.key === "ArrowDown" ? 1 : -1, opciones.length));
    } else if (e.key === "Enter" && activo >= 0 && opciones[activo]) {
      e.preventDefault();
      elegir(opciones[activo]);
    } else if (e.key === "Escape") {
      setQ("");
      setActivo(-1);
    }
  }

  // Ya hay uno elegido: el estado de reposo muestra a QUIÉN se le está vendiendo, no un buscador
  // vacío. La venta en curso tiene que poder leerse de un vistazo.
  if (elegido) {
    return (
      <div className="flex items-center justify-between gap-2 rounded-md border border-input bg-background px-3 py-2 text-sm">
        <span className="min-w-0 truncate">
          <span className="font-medium">{elegido.denominacion}</span>
          <span className="text-muted-foreground"> · {elegido.codigo}</span>
        </span>
        <button
          type="button"
          onClick={limpiar}
          className="shrink-0 rounded-md p-1 text-muted-foreground hover:bg-muted focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
          aria-label="Cambiar de cliente"
        >
          <X className="h-4 w-4" />
        </button>
      </div>
    );
  }

  const abierto = texto.length > 0;

  return (
    <div className="space-y-2">
      <div className="relative">
        <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
        <input
          ref={inputRef}
          value={q}
          onChange={(e) => {
            setQ(e.target.value);
            setActivo(-1);
          }}
          onKeyDown={onKeyDown}
          placeholder="Buscá el cliente por nombre, código o CUIT…"
          className={inputClass}
          aria-label="Cliente"
          role="combobox"
          aria-expanded={abierto}
          aria-controls="lista-clientes"
          aria-autocomplete="list"
          aria-activedescendant={activo >= 0 ? `cliente-opcion-${activo}` : undefined}
        />
      </div>

      {abierto && (
        <Card className="max-h-64 divide-y overflow-auto p-0">
          <ul id="lista-clientes" role="listbox" aria-label="Clientes que coinciden">
            {isError && (
              <li className="p-3 text-sm text-destructive" role="alert">
                No pude buscar clientes. Probá de nuevo.
              </li>
            )}
            {!isError && isFetching && opciones.length === 0 && (
              <li className="p-3 text-sm text-muted-foreground">Buscando…</li>
            )}
            {!isError && !isFetching && opciones.length === 0 && (
              <li className="p-3 text-sm text-muted-foreground">
                Sin clientes para «{texto}».
              </li>
            )}
            {/* La opción es el `li` mismo, sin un `button` adentro. Un elemento interactivo
                anidado dentro de un `role="option"` es un lector de pantalla anunciando dos
                controles donde hay uno. El teclado no se pierde: lo maneja el input, que
                conserva el foco y apunta con `aria-activedescendant`. */}
            {opciones.map((c, i) => (
              <li
                key={c.codigo}
                id={`cliente-opcion-${i}`}
                role="option"
                aria-selected={i === activo}
                // `onMouseDown` y no `onClick`: el click primero saca el foco del input, y con el
                // foco afuera la lista ya se cerró antes de que el click llegue a destino.
                onMouseDown={() => elegir(c)}
                onMouseEnter={() => setActivo(i)}
                className={`flex cursor-pointer items-center justify-between gap-3 p-3 text-left text-sm ${
                  i === activo ? "bg-muted" : ""
                }`}
              >
                <span className="min-w-0 truncate">
                  <span className="font-medium">{c.denominacion}</span>
                  <span className="text-muted-foreground"> · {c.codigo}</span>
                </span>
                {c.cuit && <span className="shrink-0 text-xs text-muted-foreground">{c.cuit}</span>}
              </li>
            ))}
          </ul>
        </Card>
      )}
    </div>
  );
}
