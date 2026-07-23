import { useProveedores } from "@/features/proveedores/model/hooks";

const selectClass =
  "h-9 w-full rounded-md border border-input bg-background px-3 text-sm focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring";

/** Elige el proveedor de la compra. El backend exige `proveedor_codigo`, así que no hay opción
 * vacía válida: mientras no se elija uno, la compra no se puede registrar. */
export function SelectorProveedor({
  value,
  onChange,
}: {
  value: string;
  onChange: (codigo: string) => void;
}) {
  const { data, isLoading, isError } = useProveedores();

  return (
    <select
      value={value}
      onChange={(e) => onChange(e.target.value)}
      className={selectClass}
      disabled={isLoading || isError}
      aria-label="Proveedor"
    >
      <option value="">
        {isLoading
          ? "Cargando proveedores…"
          : isError
            ? "No pude cargar proveedores"
            : "Elegí un proveedor…"}
      </option>
      {data
        ?.filter((p) => p.activo)
        .map((p) => (
          <option key={p.codigo} value={p.codigo}>
            {p.razon_social} · {p.codigo}
          </option>
        ))}
    </select>
  );
}
