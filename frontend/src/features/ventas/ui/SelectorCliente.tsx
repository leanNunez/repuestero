import { useEffect, useState } from "react";

import type { Cliente } from "@/entities/cliente/schema";
import { useClientes } from "@/features/clientes/model/hooks";
import { Combobox, type OpcionCombobox } from "@/shared/ui/combobox";

/** Elige el cliente de la venta. El backend exige `cliente_codigo`, así que no hay opción vacía
 * válida: mientras no se elija uno, la venta no se puede emitir.
 *
 * Era un `<select>` con los primeros clientes por orden alfabético. Con 900 en la org eso
 * significaba que **no se le podía facturar a un cliente que no estuviera en esa tanda**.
 */
export function SelectorCliente({
  value,
  onChange,
}: {
  value: string;
  onChange: (codigo: string) => void;
}) {
  const [q, setQ] = useState("");
  const [elegido, setElegido] = useState<OpcionCombobox | null>(null);

  const texto = q.trim();
  const { data, isFetching, isError } = useClientes(texto, 1);
  // Sin texto no se pide nada al servidor: una lista de clientes cualquiera no ayuda a elegir.
  const opciones = texto ? (data?.items ?? []).filter((c) => c.activo).map(aOpcion) : [];

  // El padre puede limpiar el cliente (al emitir la venta, el estado se resetea). Si eso pasa, la
  // pantalla tiene que dejar de mostrar al que estaba elegido, o miente sobre la venta en curso.
  useEffect(() => {
    if (value === "") setElegido(null);
  }, [value]);

  return (
    <Combobox
      label="Cliente"
      placeholder="Buscá el cliente por nombre, código o CUIT…"
      q={q}
      onBuscar={setQ}
      opciones={opciones}
      elegido={elegido}
      onElegir={(o) => {
        setElegido(o);
        onChange(o.clave);
        setQ("");
      }}
      onLimpiar={() => {
        setElegido(null);
        onChange("");
        setQ("");
      }}
      buscando={isFetching}
      fallo={isError}
    />
  );
}

function aOpcion(c: Cliente): OpcionCombobox {
  return { clave: c.codigo, etiqueta: c.denominacion, detalle: c.cuit };
}
