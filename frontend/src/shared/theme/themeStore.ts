import { create } from "zustand";

type Theme = "light" | "dark";

const KEY = "repuestos-theme";

function apply(theme: Theme) {
  document.documentElement.classList.toggle("dark", theme === "dark");
}

function initial(): Theme {
  return localStorage.getItem(KEY) === "dark" ? "dark" : "light";
}

interface ThemeState {
  theme: Theme;
  toggle: () => void;
}

export const useThemeStore = create<ThemeState>((set, get) => ({
  theme: initial(),
  toggle: () => {
    const next: Theme = get().theme === "dark" ? "light" : "dark";
    localStorage.setItem(KEY, next);
    apply(next);
    set({ theme: next });
  },
}));

// Aplica el tema guardado al importar el módulo (antes del primer render) → sin flash.
apply(useThemeStore.getState().theme);
