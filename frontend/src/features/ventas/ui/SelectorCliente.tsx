import { useClientes } from "@/features/clientes/model/hooks";

const selectClass =
  "h-9 w-full rounded-md border border-input bg-background px-3 text-sm focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring";

/** Elige el cliente de la venta. El backend exige `cliente_codigo`, así que no hay opción vacía
 * válida: mientras no se elija uno, la venta no se puede emitir. */
export function SelectorCliente({
  value,
  onChange,
}: {
  value: string;
  onChange: (codigo: string) => void;
}) {
  const { data, isLoading, isError } = useClientes();

  return (
    <select
      value={value}
      onChange={(e) => onChange(e.target.value)}
      className={selectClass}
      disabled={isLoading || isError}
      aria-label="Cliente"
    >
      <option value="">
        {isLoading ? "Cargando clientes…" : isError ? "No pude cargar clientes" : "Elegí un cliente…"}
      </option>
      {data
        ?.filter((c) => c.activo)
        .map((c) => (
          <option key={c.codigo} value={c.codigo}>
            {c.denominacion} · {c.codigo}
          </option>
        ))}
    </select>
  );
}
