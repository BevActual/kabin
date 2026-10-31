import { create } from "zustand";

export type ThemeMode = "dark" | "light";
export type LibrarySort = "title" | "recent" | "added" | "played";

const THEME_KEY = "kabin-theme";
const SORT_KEY = "kabin-library-sort";
const SIDEBAR_KEY = "kabin-sidebar-collapsed";

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

function readSidebarCollapsed(): boolean {
  try {
    return localStorage.getItem(SIDEBAR_KEY) === "1";
  } catch {
    return false;
  }
}

function persistSidebar(collapsed: boolean) {
  try {
    localStorage.setItem(SIDEBAR_KEY, collapsed ? "1" : "0");
  } catch {
    /* ignore */
  }
}

type UiState = {
  theme: ThemeMode;
  librarySort: LibrarySort;
  sidebarCollapsed: boolean;
  searchQuery: string;
  toast: string | null;
  setTheme: (theme: ThemeMode) => void;
  setLibrarySort: (sort: LibrarySort) => void;
  setSidebarCollapsed: (collapsed: boolean) => void;
  toggleSidebar: () => void;
  setSearchQuery: (q: string) => void;
  setToast: (toast: string | null) => void;
};

export const useUiStore = create<UiState>((set) => ({
  theme: readTheme(),
  librarySort: readSort(),
  sidebarCollapsed: readSidebarCollapsed(),
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
  setSidebarCollapsed: (sidebarCollapsed) => {
    persistSidebar(sidebarCollapsed);
    set({ sidebarCollapsed });
  },
  toggleSidebar: () => {
    set((state) => {
      const sidebarCollapsed = !state.sidebarCollapsed;
      persistSidebar(sidebarCollapsed);
      return { sidebarCollapsed };
    });
  },
  setSearchQuery: (searchQuery) => set({ searchQuery }),
  setToast: (toast) => set({ toast }),
}));
