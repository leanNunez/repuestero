import { create } from "zustand";

interface DrawerState {
  assistantOpen: boolean;
  toggleAssistant: () => void;
  closeAssistant: () => void;
  /** Nav lateral como drawer en mobile (en sm+ el sidebar es fijo y esto no aplica). */
  navOpen: boolean;
  toggleNav: () => void;
  closeNav: () => void;
}

/** Estado de los drawers del shell (copiloto derecho + nav mobile). Cliente global → Zustand. */
export const useDrawerStore = create<DrawerState>((set) => ({
  assistantOpen: false,
  toggleAssistant: () => set((s) => ({ assistantOpen: !s.assistantOpen })),
  closeAssistant: () => set({ assistantOpen: false }),
  navOpen: false,
  toggleNav: () => set((s) => ({ navOpen: !s.navOpen })),
  closeNav: () => set({ navOpen: false }),
}));
