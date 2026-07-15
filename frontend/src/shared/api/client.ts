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

export const STREAM_URL = `${API_URL}/asistente/stream`;

/** GET tipado contra el backend. Con `schema` (Zod) valida la respuesta en el boundary. */
export async function apiGet<T>(
  path: string,
  schema?: { parse: (v: unknown) => T },
): Promise<T> {
  const res = await fetch(`${API_URL}${path}`, { headers: authHeaders() });
  if (!res.ok) throw new Error(`HTTP ${res.status}`);
  const json: unknown = await res.json();
  return schema ? schema.parse(json) : (json as T);
}
