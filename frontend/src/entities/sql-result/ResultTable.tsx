import type { SqlResult } from "@/entities/message/types";
import { cn } from "@/shared/lib/cn";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/shared/ui/table";

function formatCell(v: unknown): string {
  if (v === null || v === undefined) return "—";
  if (typeof v === "object") return JSON.stringify(v);
  return String(v);
}

/** Las columnas del resultado son dinámicas: no se sabe de antemano cuál trae números.
 *  Se decide por el valor de la primera fila — si es numérico, la columna entera va a la
 *  derecha y en mono, que es la única forma de que se pueda comparar de un vistazo. */
function esNumerica(filas: SqlResult["filas"], columna: string): boolean {
  const v = filas[0]?.[columna];
  return typeof v === "number" || (typeof v === "string" && v !== "" && !isNaN(Number(v)));
}

/** Presenter puro: renderiza las filas del resultado SQL como tabla + el SQL colapsable. */
export function ResultTable({ result }: { result: SqlResult }) {
  const { sql, filas } = result;
  const columnas = filas.length > 0 ? Object.keys(filas[0]) : [];
  const numericas = new Set(columnas.filter((c) => esNumerica(filas, c)));

  return (
    <div className="mt-3 space-y-2">
      {filas.length > 0 ? (
        // Más compacta que las tablas de pantalla: esto vive dentro de una burbuja de chat.
        <Table containerClassName="rounded-md bg-transparent" className="text-xs">
          <TableHeader className="bg-background/60">
            <TableRow>
              {columnas.map((c) => (
                <TableHead
                  key={c}
                  className={cn("whitespace-nowrap px-3 py-2", numericas.has(c) && "text-right")}
                >
                  {c}
                </TableHead>
              ))}
            </TableRow>
          </TableHeader>
          <TableBody>
            {filas.map((fila, i) => (
              <TableRow key={i}>
                {columnas.map((c) => (
                  <TableCell
                    key={c}
                    className={cn(
                      "whitespace-nowrap px-3 py-2",
                      numericas.has(c) && "text-right font-mono tabular-nums",
                    )}
                  >
                    {formatCell(fila[c])}
                  </TableCell>
                ))}
              </TableRow>
            ))}
          </TableBody>
        </Table>
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
