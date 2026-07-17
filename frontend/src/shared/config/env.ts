/** Base URL del backend Repuestero. Override con VITE_API_URL en frontend/.env.local. */
export const API_URL = import.meta.env.VITE_API_URL ?? "http://localhost:8000";

/** Supabase Auth. El front sólo usa la anon key (pública) — NUNCA la service_role. */
export const SUPABASE_URL = import.meta.env.VITE_SUPABASE_URL ?? "";
export const SUPABASE_ANON_KEY = import.meta.env.VITE_SUPABASE_ANON_KEY ?? "";
