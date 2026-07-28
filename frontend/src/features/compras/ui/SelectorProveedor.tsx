import { useEffect, useState } from "react";

import type { Proveedor } from "@/entities/proveedor/schema";
import { useProveedores } from "@/features/proveedores/model/hooks";
import { Combobox, type OpcionCombobox } from "@/shared/ui/combobox";

/** Elige el proveedor de la compra. El backend exige `proveedor_codigo`, así que no hay opción
 * vacía válida: mientras no se elija uno, la compra no se puede registrar.
 *
 * Espejo de `SelectorCliente`, y por el mismo motivo: era un `<select>` con la primera página del
 * padrón, así que no se le podía comprar a un proveedor que no estuviera en ella.
 */
export function SelectorProveedor({
  value,
  onChange,
}: {
  value: string;
  onChange: (codigo: string) => void;
}) {
  const [q, setQ] = useState("");
  const [elegido, setElegido] = useState<OpcionCombobox | null>(null);

  const texto = q.trim();
  const { data, isFetching, isError } = useProveedores(texto, 1);
  const opciones = texto ? (data?.items ?? []).filter((p) => p.activo).map(aOpcion) : [];

  // Si el padre limpia el código (al registrar la compra, el estado se resetea), la pantalla
  // tiene que soltar al proveedor o miente sobre la compra en curso.
  useEffect(() => {
    if (value === "") setElegido(null);
  }, [value]);

  return (
    <Combobox
      label="Proveedor"
      placeholder="Buscá el proveedor por razón social, código o CUIT…"
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

function aOpcion(p: Proveedor): OpcionCombobox {
  return { clave: p.codigo, etiqueta: p.razon_social, detalle: p.cuit };
}
