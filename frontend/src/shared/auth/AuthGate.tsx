import type { Session } from "@supabase/supabase-js";
import { useEffect, useRef, useState, type FormEvent, type ReactNode } from "react";

import { DEMO_EMAIL, DEMO_PASSWORD } from "@/shared/config/env";
import { Button } from "@/shared/ui/button";
import { Field, FieldLabel } from "@/shared/ui/field";
import { Input } from "@/shared/ui/input";

import { debeAutoLoguear, intentarLoginDemo } from "./demo";
import { supabase, supabaseConfigurado } from "./supabase";
import { useTokenStore } from "./tokenStore";

type Fase = "cargando" | "entrando-a-la-demo" | "listo";

/** Gate de auth con Supabase. Sin sesión → intenta el auto-login de demo (si está
 * configurado); si no aplica o falla, login manual. Con sesión → mete el `access_token` en
 * el `tokenStore` (que usa el api client) y renderiza la app. Reemplaza al viejo DevTokenGate.
 *
 * El backend no cambia: valida el JWT de Supabase por JWKS y resuelve la org desde `miembros`. */
export function AuthGate({ children }: { children: ReactNode }) {
  const setToken = useTokenStore((s) => s.setToken);
  const clearToken = useTokenStore((s) => s.clearToken);
  const [fase, setFase] = useState<Fase>("cargando");
  const [autenticado, setAutenticado] = useState(false);
  // Prefill del form de login SOLO cuando de verdad se intentó el auto-login y falló (ej.
  // Supabase pausada, credenciales rotadas): así el camino de cero tipeo se preserva
  // degradado —un clic en "Entrar" alcanza— sin prefillear cuando el usuario pidió
  // explícitamente login manual (`?login=1`) o acaba de cerrar sesión en esta pestaña.
  const [prefillDemo, setPrefillDemo] = useState(false);
  // Un solo intento de auto-login por montaje: sin esto, cualquier fallo se convertiría en
  // un loop de requests contra Supabase Auth (que tiene su propio rate limit).
  const intentoDemo = useRef(false);

  useEffect(() => {
    if (!supabase) {
      setFase("listo");
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
      setFase("listo");
    };

    const arrancar = async () => {
      const { data } = await client.auth.getSession();
      if (data.session) {
        aplicar(data.session);
        return;
      }

      const intentar = !intentoDemo.current && debeAutoLoguear();
      if (intentar) {
        intentoDemo.current = true;
        setFase("entrando-a-la-demo");
        const ok = await intentarLoginDemo();
        if (ok) {
          // Se vuelve a pedir la sesión en vez de confiar en el timing del listener de
          // abajo: así el resultado del auto-login no depende de si onAuthStateChange ya
          // disparó o no para cuando esto sigue.
          const { data: nueva } = await client.auth.getSession();
          aplicar(nueva.session);
          return;
        }
      }
      setPrefillDemo(intentar); // se intentó y falló → conservar las credenciales precargadas
      aplicar(null);
    };

    void arrancar();

    // Login manual, logout y refresh automático del token pasan por acá.
    const { data: sub } = client.auth.onAuthStateChange((_evento, session) => aplicar(session));
    return () => sub.subscription.unsubscribe();
  }, [setToken, clearToken]);

  if (!supabaseConfigurado) return <ConfigFaltante />;
  if (fase === "cargando") return null;
  if (fase === "entrando-a-la-demo") return <EntrandoALaDemo />;
  if (autenticado) return <>{children}</>;
  return <Login prefillDemo={prefillDemo} />;
}

function EntrandoALaDemo() {
  return (
    <div className="mx-auto flex min-h-dvh max-w-sm flex-col items-center justify-center gap-2 p-6 text-center">
      <p className="text-sm text-muted-foreground">Entrando a la demo…</p>
    </div>
  );
}

function Login({ prefillDemo }: { prefillDemo: boolean }) {
  const [email, setEmail] = useState(prefillDemo ? DEMO_EMAIL : "");
  const [password, setPassword] = useState(prefillDemo ? DEMO_PASSWORD : "");
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
        <p className="text-sm text-muted-foreground">
          {prefillDemo
            ? "No pudimos entrar solos a la demo — probá de nuevo."
            : "Entrá para gestionar tu casa de repuestos."}
        </p>
      </div>
      <form onSubmit={submit} className="space-y-3">
        {/* Labels visibles, no solo placeholder: el placeholder desaparece al tipear y quien
            vuelve al campo a corregir se queda sin saber qué iba ahí. */}
        <Field className="gap-1.5">
          <FieldLabel htmlFor="auth-email">Email</FieldLabel>
          <Input
            id="auth-email"
            type="email"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            autoComplete="email"
            required
            className="h-10"
          />
        </Field>
        <Field className="gap-1.5">
          <FieldLabel htmlFor="auth-password">Contraseña</FieldLabel>
          <Input
            id="auth-password"
            type="password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            autoComplete="current-password"
            required
            className="h-10"
          />
        </Field>
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
