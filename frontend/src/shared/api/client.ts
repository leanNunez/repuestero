import { useTokenStore } from "@/shared/auth/tokenStore";
import { API_URL } from "@/shared/config/env";

/** Headers con el Bearer del dev-token. El backend rechaza (401) si falta o es inválido. */
export function authHeaders(): Record<string, string> {
  const { token } = useTokenStore.getState();
  return {
    "Content-Type": "application/json",
    ...(token ? { Authorization: `Bearer ${token}` } : {}),
  };
}

/** Un 401 significa que el token no sirve (vencido o mal firmado). Se limpia para volver al
 * AuthGate, en vez de dejar la app "cargada pero vacía" con un token muerto en localStorage. */
function bounceIf401(status: number): void {
  if (status === 401) useTokenStore.getState().clearToken();
}

export const STREAM_URL = `${API_URL}/asistente/stream`;

/** GET tipado contra el backend. Con `schema` (Zod) valida la respuesta en el boundary. */
export async function apiGet<T>(
  path: string,
  schema?: { parse: (v: unknown) => T },
): Promise<T> {
  const res = await fetch(`${API_URL}${path}`, { headers: authHeaders() });
  bounceIf401(res.status);
  if (!res.ok) throw new Error(`HTTP ${res.status}`);
  const json: unknown = await res.json();
  return schema ? schema.parse(json) : (json as T);
}

/** Error de la API con el status a mano.
 *
 * Existe porque en las escrituras el status ES la información: un 409 ("ya se cargó") no es
 * un fallo que haya que reintentar, es una respuesta que el usuario tiene que leer. Con un
 * `Error` pelado, la UI solo puede decir "algo salió mal". */
export class ApiError extends Error {
  // Campos declarados y asignados a mano: `erasableSyntaxOnly` (tsconfig) prohíbe los
  // parameter properties del constructor, porque no son borrables por el transpilador.
  readonly status: number;
  readonly detail: string;

  constructor(status: number, detail: string) {
    super(detail);
    this.name = "ApiError";
    this.status = status;
    this.detail = detail;
  }
}

/** POST tipado. Con `schema` (Zod) valida la respuesta en el boundary. */
export async function apiPost<T>(
  path: string,
  body: unknown,
  schema?: { parse: (v: unknown) => T },
): Promise<T> {
  const res = await fetch(`${API_URL}${path}`, {
    method: "POST",
    headers: authHeaders(),
    body: JSON.stringify(body),
  });

  if (!res.ok) {
    bounceIf401(res.status);
    // El backend manda { detail: "..." }; los 422 de Pydantic mandan un array. Se intenta
    // rescatar un mensaje útil, pero nunca se rompe por no poder parsearlo.
    let detail = `HTTP ${res.status}`;
    try {
      const json: unknown = await res.json();
      const d = (json as { detail?: unknown }).detail;
      if (typeof d === "string") detail = d;
      else if (Array.isArray(d)) detail = "Revisá los datos del formulario.";
    } catch {
      /* respuesta sin JSON: queda el genérico */
    }
    throw new ApiError(res.status, detail);
  }

  const json: unknown = await res.json();
  return schema ? schema.parse(json) : (json as T);
}
