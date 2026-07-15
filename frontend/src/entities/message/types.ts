export type Role = "user" | "assistant";

/** Una fila del resultado SQL. Las claves y tipos dependen de la consulta que arme el asistente. */
export type Row = Record<string, unknown>;

export interface SqlResult {
  sql: string | null;
  filas: Row[];
}

export interface Message {
  id: string;
  role: Role;
  content: string;
  /** true mientras el asistente está streameando este mensaje. */
  streaming: boolean;
  /** bloqueado por sospecha de prompt injection. */
  blocked?: boolean;
  /** hubo un error al procesar. */
  error?: boolean;
  /** SQL + filas del evento `resultado` (solo mensajes del asistente). */
  result?: SqlResult;
}
