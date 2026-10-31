import { Link, useRouterState } from "@tanstack/react-router";
import { useQuery } from "@tanstack/react-query";
import { Download, PanelLeft, Search, Settings, X } from "lucide-react";
import type { CSSProperties, ReactNode } from "react";
import { useEffect, useRef, useState } from "react";
import { useCabinetShortcuts } from "../hooks/useCabinetShortcuts";
import { useGamepadCabinet } from "../hooks/useGamepadCabinet";
import { useLaunchSessionEvents } from "../hooks/useLaunchSessionEvents";
import { useToastAutoDismiss } from "../hooks/useToastAutoDismiss";
import { getDownloadStatus } from "../lib/kabin-api";
import {
  getContentMode,
  modeIdFromPath,
  sectionForMode,
} from "../lib/modes";
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
  const sidebarCollapsed = useUiStore((s) => s.sidebarCollapsed);
  const toggleSidebar = useUiStore((s) => s.toggleSidebar);
  const contentMode = useUiStore((s) => s.contentMode);
  const setContentMode = useUiStore((s) => s.setContentMode);
  const pathname = useRouterState({ select: (s) => s.location.pathname });
  const mode = getContentMode(modeIdFromPath(pathname) ?? contentMode);
  const searchRef = useRef<HTMLInputElement>(null);
  const previousMode = useRef(mode.id);
  const [chromeElevated, setChromeElevated] = useState(false);
  useCabinetShortcuts(searchRef);
  useGamepadCabinet(searchRef);
  useLaunchSessionEvents();
  useToastAutoDismiss();
  useEffect(() => {
    document.documentElement.dataset.theme = theme;
  }, [theme]);
  useEffect(() => {
    setChromeElevated(false);
  }, [pathname]);
  useEffect(() => {
    const id = modeIdFromPath(pathname);
    if (id) setContentMode(id);
  }, [pathname, setContentMode]);
  useEffect(() => {
    if (previousMode.current === mode.id) return;
    previousMode.current = mode.id;
    setSearchQuery("");
  }, [mode.id, setSearchQuery]);
  const toast = useUiStore((s) => s.toast);
  const setToast = useUiStore((s) => s.setToast);
  const downloadsQuery = useQuery({
    queryKey: ["downloads"],
    queryFn: getDownloadStatus,
    refetchInterval: 4000,
  });
  const activeDownloads =
    downloadsQuery.data?.jobs.filter(
      (job) => job.status === "downloading" || job.status === "queued",
    ).length ?? 0;

  const immersive =
    pathname.startsWith("/player/") || pathname.startsWith("/read/");

  const pageTitle = titleForPath(pathname, searchQuery, mode);

  const toastBanner = toast ? (
    <div
      role="status"
      className="kabin-toast kabin-glass fixed bottom-6 left-1/2 z-50 max-w-lg -translate-x-1/2 px-4 py-3 text-[calc(14px*var(--kabin-type-scale))] text-kabin-primary"
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
      className="kabin-shell relative h-full min-h-0 bg-kabin-base text-kabin-primary"
      data-theme={theme}
      data-mode={mode.id}
      data-sidebar={sidebarCollapsed ? "collapsed" : "expanded"}
      style={{ "--kabin-mode-hue": String(mode.hue) } as CSSProperties}
    >
      <Sidebar collapsed={sidebarCollapsed} />
      <div className="kabin-content-pane min-w-0">
        <header className="pointer-events-none absolute inset-x-0 top-0 z-20 px-6 pt-3">
          <div
            className={`pointer-events-auto flex items-center gap-3 px-3 py-2 ${
              chromeElevated ? "kabin-glass kabin-glass-strong" : "kabin-glass"
            }`}
          >
            <button
              type="button"
              onClick={toggleSidebar}
              aria-label={sidebarCollapsed ? "Show sidebar" : "Hide sidebar"}
              aria-pressed={!sidebarCollapsed}
              aria-keyshortcuts="Control+\\"
              className="inline-flex h-9 w-9 shrink-0 items-center justify-center rounded-full text-kabin-secondary transition-colors hover:bg-[color-mix(in_srgb,var(--kabin-label-primary)_8%,transparent)] hover:text-kabin-primary"
            >
              <PanelLeft size={20} strokeWidth={1.5} />
            </button>
            <span
              className={`min-w-0 flex-1 truncate text-[calc(17px*var(--kabin-type-scale))] font-semibold tracking-tight transition-opacity duration-200 ${
                chromeElevated ? "opacity-100" : "opacity-0"
              }`}
              aria-hidden={!chromeElevated}
            >
              {pageTitle}
            </span>
            {activeDownloads > 0 ? (
              <Link
                to="/downloads"
                className="kabin-activity-capsule shrink-0 text-[calc(13px*var(--kabin-type-scale))]"
                aria-label={`${activeDownloads} active downloads`}
              >
                <Download size={15} strokeWidth={1.75} />
                {activeDownloads}
              </Link>
            ) : null}
            <label className="relative min-w-[7.5rem] max-w-64 flex-1">
              <Search
                className="pointer-events-none absolute top-1/2 left-3 -translate-y-1/2 text-kabin-secondary"
                size={16}
                strokeWidth={1.5}
              />
              <input
                ref={searchRef}
                type="search"
                placeholder={`Search ${mode.label}`}
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                className="kabin-search w-full py-1.5 pr-8 pl-9 text-[calc(14px*var(--kabin-type-scale))] text-kabin-primary placeholder:text-kabin-tertiary focus:shadow-[var(--kabin-focus-ring)] focus:outline-none"
              />
              {searchQuery ? (
                <button
                  type="button"
                  aria-label="Clear search"
                  onClick={() => setSearchQuery("")}
                  className="absolute top-1/2 right-2 inline-flex h-6 w-6 -translate-y-1/2 items-center justify-center rounded-full text-kabin-secondary hover:bg-kabin-grouped hover:text-kabin-primary"
                >
                  <X size={14} strokeWidth={1.75} />
                </button>
              ) : null}
            </label>
            <Link
              to="/settings"
              className={`inline-flex h-9 w-9 shrink-0 items-center justify-center rounded-full transition-colors ${
                pathname === "/settings"
                  ? "kabin-sidebar-active text-kabin-accent"
                  : "text-kabin-secondary hover:bg-[color-mix(in_srgb,var(--kabin-label-primary)_8%,transparent)] hover:text-kabin-primary"
              }`}
              aria-label="Settings"
              aria-current={pathname === "/settings" ? "page" : undefined}
            >
              <Settings size={20} strokeWidth={1.5} />
            </Link>
          </div>
        </header>
        <main
          key={pathname}
          onScroll={(event) => {
            const elevated = event.currentTarget.scrollTop > 36;
            setChromeElevated((current) =>
              current === elevated ? current : elevated,
            );
          }}
          className="kabin-page-enter kabin-scroll-under-chrome h-full min-h-0 overflow-auto px-6 pb-10"
        >
          <h1 className="kabin-large-title">{pageTitle}</h1>
          {searchQuery.trim() ? <SearchView /> : children}
        </main>
        {toastBanner}
      </div>
    </div>
  );
}

function titleForPath(
  pathname: string,
  searchQuery: string,
  mode: ReturnType<typeof getContentMode>,
) {
  if (searchQuery.trim()) return "Search";
  if (pathname === `/browse/${mode.id}`) return mode.label;
  const sectionId = pathname.match(/^\/browse\/[^/]+\/([^/]+)/)?.[1];
  if (sectionId) {
    return sectionForMode(mode, sectionId)?.label ?? mode.label;
  }
  if (pathname.startsWith("/title/")) return "Details";
  if (pathname.startsWith("/player/")) return "Now Playing";
  if (pathname.startsWith("/read/")) return "Reader";
  if (pathname === "/downloads") return "Downloads";
  if (pathname === "/settings") return "Settings";
  return mode.label;
}
