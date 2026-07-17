import { useEffect, useState, type FormEvent, type ReactNode } from "react";

import { Button } from "@/shared/ui/button";
import { Textarea } from "@/shared/ui/textarea";

import { useTokenStore } from "./tokenStore";

/** ¿El JWT sigue vigente? Decodifica el payload (base64url) y mira `exp`.
 *
 * No valida la firma —el browser no tiene el secreto y no debe tenerlo—: solo evita que un
 * token vencido o malformado pase el gate y deje la app "cargada pero vacía" (todas las
 * llamadas darían 401). La firma la valida el backend; un 401 igual limpia el token. */
function tokenVigente(token: string): boolean {
  try {
    const payload = token.split(".")[1].replace(/-/g, "+").replace(/_/g, "/");
    const { exp } = JSON.parse(atob(payload)) as { exp?: number };
    return typeof exp === "number" && exp * 1000 > Date.now();
  } catch {
    return false;
  }
}

/** Gate de dev: sin token válido, pide pegar un JWT. Con token vigente, renderiza la app.
 * No es auth de producción. */
export function DevTokenGate({ children }: { children: ReactNode }) {
  const token = useTokenStore((s) => s.token);
  const setToken = useTokenStore((s) => s.setToken);
  const clearToken = useTokenStore((s) => s.clearToken);
  const [draft, setDraft] = useState("");

  const valido = token !== null && tokenVigente(token);

  // Un token persistido pero vencido/roto se descarta: mejor volver a pedirlo que fingir sesión.
  useEffect(() => {
    if (token !== null && !valido) clearToken();
  }, [token, valido, clearToken]);

  if (valido) return <>{children}</>;

  const submit = (e: FormEvent) => {
    e.preventDefault();
    if (draft.trim()) setToken(draft);
  };

  return (
    <div className="mx-auto flex min-h-dvh max-w-md flex-col justify-center gap-4 p-6">
      <div className="space-y-1">
        <h1 className="text-lg font-semibold">Token de desarrollo</h1>
        <p className="text-sm text-muted-foreground">
          Pegá un JWT de dev para hablar con el asistente. Generalo con{" "}
          <code className="rounded bg-muted px-1 py-0.5 font-mono text-xs">
            scratchpad/gen_jwt.py
          </code>
          .
        </p>
      </div>
      <form onSubmit={submit} className="space-y-3">
        <Textarea
          value={draft}
          onChange={(e) => setDraft(e.target.value)}
          rows={4}
          placeholder="eyJhbGciOi…"
          aria-label="JWT de desarrollo"
          className="font-mono text-xs"
        />
        <Button type="submit" disabled={draft.trim().length === 0} className="w-full">
          Guardar y entrar
        </Button>
      </form>
    </div>
  );
}
