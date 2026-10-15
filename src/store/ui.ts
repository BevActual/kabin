import { create } from "zustand";

export type ThemeMode = "dark" | "light";

type UiState = {
  theme: ThemeMode;
  searchQuery: string;
  toast: string | null;
  setTheme: (theme: ThemeMode) => void;
  setSearchQuery: (q: string) => void;
  setToast: (toast: string | null) => void;
};

export const useUiStore = create<UiState>((set) => ({
  theme: "dark",
  searchQuery: "",
  toast: null,
  setTheme: (theme) => set({ theme }),
  setSearchQuery: (searchQuery) => set({ searchQuery }),
  setToast: (toast) => set({ toast }),
}));
