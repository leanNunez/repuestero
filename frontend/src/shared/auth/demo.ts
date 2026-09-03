import { DEMO_EMAIL, DEMO_MODE, DEMO_PASSWORD } from "@/shared/config/env";

import { supabase } from "./supabase";

const SALIDA_EXPLICITA_KEY = "repuestero-demo-off";

/** `sessionStorage`, no `localStorage`, a propósito: la salida explícita dura lo que dura
 * ESTA pestaña. La próxima pestaña — o el próximo visitante — vuelve a entrar directo a la
 * demo, que es lo que un segundo reclutador espera. Que alguien haya cerrado sesión en una
 * pestaña no debería dejar bloqueada a la siguiente. */
export function marcarSalidaExplicita(): void {
  try {
    sessionStorage.setItem(SALIDA_EXPLICITA_KEY, "1");
  } catch {
    /* sessionStorage bloqueado (ventana privada estricta, etc.): el logout sigue andando */
  }
}

function salioExplicitamente(): boolean {
  try {
    return sessionStorage.getItem(SALIDA_EXPLICITA_KEY) === "1";
  } catch {
    return false;
  }
}

/** `?login=1` en la URL saltea el auto-login: la vía de escape para vos, no para la demo. */
export function pideLoginManual(): boolean {
  try {
    return new URLSearchParams(window.location.search).get("login") === "1";
  } catch {
    return false;
  }
}

/** Si esto da true, el `AuthGate` intenta el auto-login ANTES de mostrar el formulario. */
export function debeAutoLoguear(): boolean {
  return DEMO_MODE && !salioExplicitamente() && !pideLoginManual();
}

/** Un solo intento (lo garantiza el caller con un `useRef`, no esta función): reintentar en
 * cada render sería un loop contra Supabase Auth, que además tiene su propio rate limit y
 * puede terminar bloqueando el proyecto entero, no solo esta sesión. */
export async function intentarLoginDemo(): Promise<boolean> {
  if (!supabase) return false;
  const { error } = await supabase.auth.signInWithPassword({
    email: DEMO_EMAIL,
    password: DEMO_PASSWORD,
  });
  return !error;
}

// --------------------------------------------------------------------- banner de demo ---

const BANNER_CERRADO_KEY = "repuestero-banner-demo-cerrado";

/** También por sesión (pestaña), como la salida explícita: quien cierra el aviso no lo ve
 * más en ESTA visita, pero el próximo visitante lo ve de nuevo. */
export function bannerDemoCerrado(): boolean {
  try {
    return sessionStorage.getItem(BANNER_CERRADO_KEY) === "1";
  } catch {
    return false;
  }
}

export function cerrarBannerDemo(): void {
  try {
    sessionStorage.setItem(BANNER_CERRADO_KEY, "1");
  } catch {
    /* sessionStorage bloqueado: el banner se puede volver a cerrar en el próximo render */
  }
}
