import { createClient, type SupabaseClient } from "@supabase/supabase-js";

import { SUPABASE_ANON_KEY, SUPABASE_URL } from "@/shared/config/env";

/** ¿Hay config de Supabase? Sin ella (ej. local sin configurar) el gate lo avisa en vez de
 * que `createClient` explote con un string vacío. */
export const supabaseConfigurado = Boolean(SUPABASE_URL && SUPABASE_ANON_KEY);

/** Cliente de Supabase Auth. Sólo emite y auto-renueva JWTs; el backend los valida por JWKS
 * (`app/core/security.py`). La sesión se persiste en localStorage. `null` si falta config. */
export const supabase: SupabaseClient | null = supabaseConfigurado
  ? createClient(SUPABASE_URL, SUPABASE_ANON_KEY, {
      auth: {
        persistSession: true,
        autoRefreshToken: true,
        detectSessionInUrl: false,
      },
    })
  : null;
