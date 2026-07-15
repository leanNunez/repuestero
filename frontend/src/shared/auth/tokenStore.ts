import { create } from "zustand";
import { persist } from "zustand/middleware";

interface TokenState {
  /** JWT de dev (HS256 auto-firmado). NO es auth de producción: se reemplaza por Supabase Auth. */
  token: string | null;
  setToken: (t: string) => void;
  clearToken: () => void;
}

export const useTokenStore = create<TokenState>()(
  persist(
    (set) => ({
      token: null,
      setToken: (token) => set({ token: token.trim() || null }),
      clearToken: () => set({ token: null }),
    }),
    { name: "repuestos-dev-token" },
  ),
);
