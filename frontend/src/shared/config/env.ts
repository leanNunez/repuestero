/** Base URL del backend Repuestero. Override con VITE_API_URL en frontend/.env.local. */
export const API_URL = import.meta.env.VITE_API_URL ?? "http://localhost:8000";

/** Supabase Auth. El front sólo usa la anon key (pública) — NUNCA la service_role. */
export const SUPABASE_URL = import.meta.env.VITE_SUPABASE_URL ?? "";
export const SUPABASE_ANON_KEY = import.meta.env.VITE_SUPABASE_ANON_KEY ?? "";

/** Credenciales del auto-login de demo. Ya son públicas (README.md): entrar sin tipear nada
 * usa las mismas que hoy hay que copiar a mano. Sin AMBAS, DEMO_MODE queda en false y el
 * comportamiento es el de siempre (pantalla de login) — así un `bun dev` local no se
 * auto-loguea contra la demo por accidente. Ver shared/auth/demo.ts. */
export const DEMO_EMAIL = import.meta.env.VITE_DEMO_EMAIL ?? "";
export const DEMO_PASSWORD = import.meta.env.VITE_DEMO_PASSWORD ?? "";
export const DEMO_MODE = Boolean(DEMO_EMAIL && DEMO_PASSWORD);
