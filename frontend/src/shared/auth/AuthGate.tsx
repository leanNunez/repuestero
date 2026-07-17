import type { Session } from "@supabase/supabase-js";
import { useEffect, useState, type FormEvent, type ReactNode } from "react";

import { Button } from "@/shared/ui/button";

import { supabase, supabaseConfigurado } from "./supabase";
import { useTokenStore } from "./tokenStore";

const inputClass =
  "h-10 w-full rounded-md border border-input bg-background px-3 text-sm focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring";

/** Gate de auth con Supabase. Sin sesión → login; con sesión → mete el `access_token` en el
 * `tokenStore` (que usa el api client) y renderiza la app. Reemplaza al viejo DevTokenGate.
 *
 * El backend no cambia: valida el JWT de Supabase por JWKS y resuelve la org desde `miembros`. */
export function AuthGate({ children }: { children: ReactNode }) {
  const setToken = useTokenStore((s) => s.setToken);
  const clearToken = useTokenStore((s) => s.clearToken);
  const [listo, setListo] = useState(false);
  const [autenticado, setAutenticado] = useState(false);

  useEffect(() => {
    if (!supabase) {
      setListo(true);
      return;
    }
    const client = supabase;

    // El access_token de Supabase ES la única fuente de verdad del token del api client.
    const aplicar = (session: Session | null) => {
      if (session?.access_token) {
        setToken(session.access_token);
        setAutenticado(true);
      } else {
        clearToken();
        setAutenticado(false);
      }
    };

    void client.auth.getSession().then(({ data }) => {
      aplicar(data.session);
      setListo(true);
    });
    // Login, logout y refresh automático del token pasan por acá.
    const { data: sub } = client.auth.onAuthStateChange((_evento, session) => aplicar(session));
    return () => sub.subscription.unsubscribe();
  }, [setToken, clearToken]);

  if (!supabaseConfigurado) return <ConfigFaltante />;
  if (!listo) return null;
  if (autenticado) return <>{children}</>;
  return <Login />;
}

function Login() {
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [cargando, setCargando] = useState(false);

  const submit = async (e: FormEvent) => {
    e.preventDefault();
    if (!supabase) return;
    setCargando(true);
    setError(null);
    const { error: err } = await supabase.auth.signInWithPassword({ email, password });
    setCargando(false);
    if (err) setError("No pudimos entrar. Revisá el email y la contraseña.");
  };

  return (
    <div className="mx-auto flex min-h-dvh max-w-sm flex-col justify-center gap-6 p-6">
      <div className="space-y-1 text-center">
        <h1 className="text-2xl font-bold tracking-tight">Repuestero</h1>
        <p className="text-sm text-muted-foreground">Entrá para gestionar tu casa de repuestos.</p>
      </div>
      <form onSubmit={submit} className="space-y-3">
        <input
          type="email"
          value={email}
          onChange={(e) => setEmail(e.target.value)}
          placeholder="Email"
          autoComplete="email"
          required
          aria-label="Email"
          className={inputClass}
        />
        <input
          type="password"
          value={password}
          onChange={(e) => setPassword(e.target.value)}
          placeholder="Contraseña"
          autoComplete="current-password"
          required
          aria-label="Contraseña"
          className={inputClass}
        />
        <Button type="submit" disabled={cargando} className="w-full">
          {cargando ? "Entrando…" : "Entrar"}
        </Button>
      </form>
      {error && (
        <p role="alert" className="text-center text-sm font-medium text-destructive">
          {error}
        </p>
      )}
    </div>
  );
}

function ConfigFaltante() {
  return (
    <div className="mx-auto flex min-h-dvh max-w-md flex-col justify-center gap-2 p-6 text-center">
      <h1 className="text-lg font-semibold">Falta configurar Supabase</h1>
      <p className="text-sm text-muted-foreground">
        Definí <code className="font-mono">VITE_SUPABASE_URL</code> y{" "}
        <code className="font-mono">VITE_SUPABASE_ANON_KEY</code> en el entorno del front (ver{" "}
        <code className="font-mono">frontend/env.example</code>).
      </p>
    </div>
  );
}
