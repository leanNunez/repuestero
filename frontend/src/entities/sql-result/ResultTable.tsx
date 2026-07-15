import type { SqlResult } from "@/entities/message/types";

function formatCell(v: unknown): string {
  if (v === null || v === undefined) return "—";
  if (typeof v === "object") return JSON.stringify(v);
  return String(v);
}

/** Presenter puro: renderiza las filas del resultado SQL como tabla + el SQL colapsable. */
export function ResultTable({ result }: { result: SqlResult }) {
  const { sql, filas } = result;
  const columnas = filas.length > 0 ? Object.keys(filas[0]) : [];

  return (
    <div className="mt-3 space-y-2">
      {filas.length > 0 ? (
        <div className="overflow-x-auto rounded-md border border-border">
          <table className="w-full text-left text-xs">
            <thead className="bg-background/60 text-muted-foreground">
              <tr>
                {columnas.map((c) => (
                  <th key={c} className="whitespace-nowrap px-3 py-2 font-medium">
                    {c}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {filas.map((fila, i) => (
                <tr key={i} className="border-t border-border">
                  {columnas.map((c) => (
                    <td key={c} className="whitespace-nowrap px-3 py-2 tabular-nums">
                      {formatCell(fila[c])}
                    </td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : (
        <p className="text-xs text-muted-foreground">La consulta no devolvió filas.</p>
      )}

      {sql && (
        <details className="group">
          <summary className="cursor-pointer select-none text-xs text-muted-foreground hover:text-foreground">
            ver SQL
          </summary>
          <pre className="mt-1 overflow-x-auto rounded-md bg-background/60 p-3 font-mono text-xs">
            {sql}
          </pre>
        </details>
      )}
    </div>
  );
}
