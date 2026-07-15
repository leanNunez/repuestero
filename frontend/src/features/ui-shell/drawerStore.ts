import { create } from "zustand";

interface DrawerState {
  assistantOpen: boolean;
  toggleAssistant: () => void;
  closeAssistant: () => void;
}

/** Estado del drawer del copiloto (abierto/cerrado). Cliente global → Zustand. */
export const useDrawerStore = create<DrawerState>((set) => ({
  assistantOpen: false,
  toggleAssistant: () => set((s) => ({ assistantOpen: !s.assistantOpen })),
  closeAssistant: () => set({ assistantOpen: false }),
}));
