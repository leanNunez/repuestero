import { Search, X } from "lucide-react";
import { useRef, useState } from "react";

import { moverIndice } from "@/shared/lib/lista";

import { Input } from "./input";

/** Una opción del combobox, ya normalizada. La entidad concreta (cliente, proveedor) se mapea a
 *  esto en su selector: acá adentro no se sabe qué se está eligiendo, y está bien que no se sepa. */
export interface OpcionCombobox {
  /** Lo que se devuelve al elegir. En este proyecto siempre es el código. */
  clave: string;
  /** Lo que se lee: denominación o razón social. */
  etiqueta: string;
  /** Dato secundario a la derecha (el CUIT). Opcional. */
  detalle?: string | null;
}

interface Props {
  /** Para el `aria-label` del input y el del listado. "Cliente", "Proveedor". */
  label: string;
  placeholder: string;
  /** Texto buscado. Lo controla el padre porque es lo que dispara su consulta al servidor. */
  q: string;
  onBuscar: (q: string) => void;
  opciones: OpcionCombobox[];
  elegido: OpcionCombobox | null;
  onElegir: (o: OpcionCombobox) => void;
  onLimpiar: () => void;
  buscando: boolean;
  fallo: boolean;
}

/** Buscador con lista desplegable, teclado y semántica de combobox.
 *
 * Existe porque clientes y proveedores necesitan lo mismo, y el teclado más las ARIA son
 * exactamente lo que no conviene mantener por duplicado: si se arreglan en un lado y no en el
 * otro, la pantalla que quedó vieja no falla — simplemente deja afuera a quien no usa mouse.
 *
 * El foco NUNCA se va del input: las opciones no son focusables y se apunta a la activa con
 * `aria-activedescendant`. Es el patrón de combobox de WAI-ARIA, y es lo que permite seguir
 * escribiendo mientras se navega la lista.
 */
export function Combobox({
  label,
  placeholder,
  q,
  onBuscar,
  opciones,
  elegido,
  onElegir,
  onLimpiar,
  buscando,
  fallo,
}: Props) {
  const [activo, setActivo] = useState(-1);
  const inputRef = useRef<HTMLInputElement>(null);

  const texto = q.trim();
  const abierto = texto.length > 0;
  const idLista = `lista-${label.toLowerCase()}`;

  function elegir(o: OpcionCombobox) {
    onElegir(o);
    setActivo(-1);
  }

  function onKeyDown(e: React.KeyboardEvent<HTMLInputElement>) {
    if (e.key === "ArrowDown" || e.key === "ArrowUp") {
      // Sin `preventDefault` la flecha mueve el cursor dentro del texto: la lista y el cursor
      // pelean por la misma tecla.
      e.preventDefault();
      setActivo((i) => moverIndice(i, e.key === "ArrowDown" ? 1 : -1, opciones.length));
    } else if (e.key === "Enter" && activo >= 0 && opciones[activo]) {
      // Con nada resaltado, Enter NO elige: escribir y apretar Enter para confirmar el texto no
      // puede terminar eligiendo al primero de la lista.
      e.preventDefault();
      elegir(opciones[activo]);
    } else if (e.key === "Escape") {
      onBuscar("");
      setActivo(-1);
    }
  }

  // Ya hay uno elegido: el estado de reposo muestra QUÉ se eligió, no un buscador vacío. La
  // operación en curso tiene que poder leerse de un vistazo.
  if (elegido) {
    return (
      <div className="flex items-center justify-between gap-2 rounded-md border border-input bg-background px-3 py-2 text-sm">
        <span className="min-w-0 truncate">
          <span className="font-medium">{elegido.etiqueta}</span>
          <span className="text-muted-foreground"> · {elegido.clave}</span>
        </span>
        <button
          type="button"
          onClick={() => {
            onLimpiar();
            setActivo(-1);
            inputRef.current?.focus();
          }}
          className="shrink-0 rounded-md p-1 text-muted-foreground hover:bg-muted focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
          aria-label={`Cambiar de ${label.toLowerCase()}`}
        >
          <X className="h-4 w-4" />
        </button>
      </div>
    );
  }

  return (
    <div className="space-y-2">
      <div className="relative">
        <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
        <Input
          ref={inputRef}
          value={q}
          onChange={(e) => {
            onBuscar(e.target.value);
            setActivo(-1);
          }}
          onKeyDown={onKeyDown}
          placeholder={placeholder}
          className="pl-10"
          aria-label={label}
          role="combobox"
          aria-expanded={abierto}
          aria-controls={idLista}
          aria-autocomplete="list"
          aria-activedescendant={activo >= 0 ? `${idLista}-opcion-${activo}` : undefined}
        />
      </div>

      {abierto && (
        <div className="max-h-64 overflow-auto rounded-lg border border-border bg-card">
          <ul id={idLista} role="listbox" aria-label={`${label}s que coinciden`}>
            {fallo && (
              <li className="p-3 text-sm text-destructive" role="alert">
                No pude buscar. Probá de nuevo.
              </li>
            )}
            {!fallo && buscando && opciones.length === 0 && (
              <li className="p-3 text-sm text-muted-foreground">Buscando…</li>
            )}
            {!fallo && !buscando && opciones.length === 0 && (
              <li className="p-3 text-sm text-muted-foreground">Sin resultados para «{texto}».</li>
            )}
            {/* La opción es el `li` mismo, sin un `button` adentro: un elemento interactivo
                anidado dentro de un `role="option"` es un lector de pantalla anunciando dos
                controles donde hay uno. */}
            {opciones.map((o, i) => (
              <li
                key={o.clave}
                id={`${idLista}-opcion-${i}`}
                role="option"
                aria-selected={i === activo}
                // `onMouseDown` y no `onClick`: el click primero saca el foco del input, y con el
                // foco afuera la lista ya se cerró antes de que el click llegue a destino.
                onMouseDown={() => elegir(o)}
                onMouseEnter={() => setActivo(i)}
                className={`flex cursor-pointer items-center justify-between gap-3 border-b border-border p-3 text-left text-sm last:border-0 ${
                  i === activo ? "bg-muted" : ""
                }`}
              >
                <span className="min-w-0 truncate">
                  <span className="font-medium">{o.etiqueta}</span>
                  <span className="text-muted-foreground"> · {o.clave}</span>
                </span>
                {o.detalle && (
                  <span className="shrink-0 text-xs text-muted-foreground">{o.detalle}</span>
                )}
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );
}
