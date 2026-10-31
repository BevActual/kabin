import { create } from "zustand";

export type ThemeMode = "dark" | "light";
export type LibrarySort = "title" | "recent" | "added" | "played";

const THEME_KEY = "kabin-theme";
const SORT_KEY = "kabin-library-sort";

function readTheme(): ThemeMode {
  try {
    return localStorage.getItem(THEME_KEY) === "light" ? "light" : "dark";
  } catch {
    return "dark";
  }
}

function readSort(): LibrarySort {
  try {
    const value = localStorage.getItem(SORT_KEY);
    if (
      value === "title" ||
      value === "recent" ||
      value === "added" ||
      value === "played"
    ) {
      return value;
    }
  } catch {
    /* ignore */
  }
  return "title";
}

type UiState = {
  theme: ThemeMode;
  librarySort: LibrarySort;
  searchQuery: string;
  toast: string | null;
  setTheme: (theme: ThemeMode) => void;
  setLibrarySort: (sort: LibrarySort) => void;
  setSearchQuery: (q: string) => void;
  setToast: (toast: string | null) => void;
};

export const useUiStore = create<UiState>((set) => ({
  theme: readTheme(),
  librarySort: readSort(),
  searchQuery: "",
  toast: null,
  setTheme: (theme) => {
    try {
      localStorage.setItem(THEME_KEY, theme);
    } catch {
      /* ignore */
    }
    set({ theme });
  },
  setLibrarySort: (librarySort) => {
    try {
      localStorage.setItem(SORT_KEY, librarySort);
    } catch {
      /* ignore */
    }
    set({ librarySort });
  },
  setSearchQuery: (searchQuery) => set({ searchQuery }),
  setToast: (toast) => set({ toast }),
}));
