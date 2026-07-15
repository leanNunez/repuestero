import { useState, type FormEvent, type ReactNode } from "react";

import { Button } from "@/shared/ui/button";
import { Textarea } from "@/shared/ui/textarea";

import { useTokenStore } from "./tokenStore";

/** Gate de dev: sin token, pide pegar un JWT. Con token, renderiza la app. No es auth de producción. */
export function DevTokenGate({ children }: { children: ReactNode }) {
  const token = useTokenStore((s) => s.token);
  const setToken = useTokenStore((s) => s.setToken);
  const [draft, setDraft] = useState("");

  if (token) return <>{children}</>;

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
