import { create } from "zustand";

export type ThemeMode = "dark" | "light";

type UiState = {
  theme: ThemeMode;
  searchQuery: string;
  setTheme: (theme: ThemeMode) => void;
  setSearchQuery: (q: string) => void;
};

export const useUiStore = create<UiState>((set) => ({
  theme: "dark",
  searchQuery: "",
  setTheme: (theme) => set({ theme }),
  setSearchQuery: (searchQuery) => set({ searchQuery }),
}));
