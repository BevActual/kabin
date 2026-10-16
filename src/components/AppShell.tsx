import { Link, useRouterState } from "@tanstack/react-router";
import { Search, Settings } from "lucide-react";
import type { ReactNode } from "react";
import { useRef } from "react";
import { useCabinetShortcuts } from "../hooks/useCabinetShortcuts";
import { useGamepadCabinet } from "../hooks/useGamepadCabinet";
import { useLaunchSessionEvents } from "../hooks/useLaunchSessionEvents";
import { useToastAutoDismiss } from "../hooks/useToastAutoDismiss";
import { useUiStore } from "../store/ui";
import { SearchView } from "../routes/SearchView";
import { Sidebar } from "./Sidebar";

type Props = {
  children: ReactNode;
};

export function AppShell({ children }: Props) {
  const theme = useUiStore((s) => s.theme);
  const searchQuery = useUiStore((s) => s.searchQuery);
  const setSearchQuery = useUiStore((s) => s.setSearchQuery);
  const pathname = useRouterState({ select: (s) => s.location.pathname });
  const searchRef = useRef<HTMLInputElement>(null);
  useCabinetShortcuts(searchRef);
  useGamepadCabinet(searchRef);
  useLaunchSessionEvents();
  useToastAutoDismiss();
  const toast = useUiStore((s) => s.toast);
  const setToast = useUiStore((s) => s.setToast);

  const immersive =
    pathname.startsWith("/player/") || pathname.startsWith("/read/");

  const pageTitle =
    pathname === "/"
      ? "Home"
      : pathname.startsWith("/library/")
        ? libraryLabel(pathname.split("/").pop() ?? "")
        : pathname.startsWith("/title/")
          ? "Details"
          : pathname.startsWith("/player/")
            ? "Now Playing"
            : pathname.startsWith("/read/")
              ? "Reader"
              : pathname === "/settings"
                ? "Settings"
                : "Kabin";

  const toastBanner = toast ? (
    <div
      role="status"
      className="kabin-toast fixed bottom-6 left-1/2 z-50 max-w-lg -translate-x-1/2 rounded-[var(--kabin-radius-sheet)] border border-kabin-separator bg-kabin-elevated px-4 py-3 text-[calc(14px*var(--kabin-type-scale))] text-kabin-primary shadow-[var(--kabin-shadow-tile-focus)]"
    >
      <div className="flex items-start gap-3">
        <p className="flex-1">{toast}</p>
        <button
          type="button"
          className="text-kabin-secondary hover:text-kabin-primary"
          onClick={() => setToast(null)}
        >
          Dismiss
        </button>
      </div>
    </div>
  ) : null;

  if (immersive) {
    return (
      <div
        className="flex h-full min-h-0 bg-kabin-base text-kabin-primary"
        data-theme={theme}
      >
        <main className="kabin-page-enter min-h-0 flex-1 overflow-auto px-4 pb-8 sm:px-6">
          {children}
        </main>
        {toastBanner}
      </div>
    );
  }

  return (
    <div
      className="flex h-full min-h-0 bg-kabin-base text-kabin-primary"
      data-theme={theme}
    >
      <Sidebar />
      <div className="flex min-w-0 flex-1 flex-col">
        <header className="kabin-material-bar flex shrink-0 items-center gap-4 px-6 py-4">
          <h1 className="min-w-0 flex-1 truncate text-[calc(28px*var(--kabin-type-scale))] font-semibold tracking-tight">
            {pageTitle}
          </h1>
          <label className="relative hidden max-w-md flex-1 sm:block">
            <Search
              className="pointer-events-none absolute top-1/2 left-3 -translate-y-1/2 text-kabin-secondary"
              size={18}
              strokeWidth={1.5}
            />
            <input
              ref={searchRef}
              type="search"
              placeholder="Search"
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              className="w-full rounded-[var(--kabin-radius-control)] border border-kabin-separator bg-kabin-elevated py-2 pr-3 pl-10 text-[calc(15px*var(--kabin-type-scale))] text-kabin-primary placeholder:text-kabin-tertiary focus:shadow-[var(--kabin-focus-ring)] focus:outline-none"
            />
          </label>
          <Link
            to="/settings"
            className="inline-flex h-9 w-9 items-center justify-center rounded-[var(--kabin-radius-control)] text-kabin-secondary transition-colors hover:bg-kabin-grouped hover:text-kabin-primary"
            aria-label="Settings"
          >
            <Settings size={20} strokeWidth={1.5} />
          </Link>
        </header>
        <main
          key={pathname}
          className="kabin-page-enter min-h-0 flex-1 overflow-auto px-6 pb-8"
        >
          {searchQuery.trim() ? <SearchView /> : children}
        </main>
        {toastBanner}
      </div>
    </div>
  );
}

function libraryLabel(kind: string) {
  const labels: Record<string, string> = {
    game: "Games",
    music: "Music",
    video: "Movies",
    book: "Books",
    comic: "Comics",
    favorites: "Favorites",
  };
  return labels[kind] ?? "Library";
}
