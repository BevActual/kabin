import { Link, useRouterState } from "@tanstack/react-router";
import { useQuery } from "@tanstack/react-query";
import { Download, PanelLeft } from "lucide-react";
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
import { AudioEngine } from "./AudioEngine";
import { QuickLook } from "./QuickLook";
import { Sidebar } from "./Sidebar";
import { TransportBar } from "./TransportBar";
import { useTransportStore } from "../store/transport";

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
  const setPreviewTitleId = useUiStore((s) => s.setPreviewTitleId);
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
    setPreviewTitleId(null);
  }, [pathname, setPreviewTitleId]);
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
  const transportVisible = useTransportStore((s) => !!(s.audio || s.reading));

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

  return (
    <>
      <AudioEngine />
      {immersive ? (
    <div
      className="flex h-full min-h-0 bg-kabin-base text-kabin-primary"
      data-theme={theme}
    >
        <main className="kabin-page-enter min-h-0 flex-1 overflow-auto px-4 pb-8 sm:px-6">
          {children}
        </main>
        {toastBanner}
      </div>
      ) : (
    <div
      className="kabin-shell relative h-full min-h-0 bg-kabin-base text-kabin-primary"
      data-theme={theme}
      data-mode={mode.id}
      data-sidebar={sidebarCollapsed ? "collapsed" : "expanded"}
      style={{ "--kabin-mode-hue": String(mode.hue) } as CSSProperties}
    >
      <Sidebar collapsed={sidebarCollapsed} searchRef={searchRef} />
      <div className="kabin-content-pane min-w-0">
        <header className="pointer-events-none absolute top-3 left-6 z-20">
          <div
            className={`pointer-events-auto inline-flex max-w-full items-center gap-0.5 py-1 pr-1 pl-1 ${
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
            {chromeElevated ? (
              <span className="kabin-page-enter max-w-52 truncate pr-2 text-[calc(15px*var(--kabin-type-scale))] font-semibold tracking-tight">
                {pageTitle}
              </span>
            ) : null}
            {activeDownloads > 0 ? (
              <Link
                to="/downloads"
                className="kabin-activity-capsule mr-1 shrink-0 text-[calc(13px*var(--kabin-type-scale))]"
                aria-label={`${activeDownloads} active downloads`}
              >
                <Download size={15} strokeWidth={1.75} />
                {activeDownloads}
              </Link>
            ) : null}
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
          className={`kabin-page-enter kabin-scroll-under-chrome h-full min-h-0 overflow-auto px-6 ${
            transportVisible ? "pb-24" : "pb-10"
          }`}
        >
          {pathname.startsWith("/title/") && !searchQuery.trim() ? null : (
            <h1 className="kabin-large-title">{pageTitle}</h1>
          )}
          {searchQuery.trim() ? <SearchView /> : children}
        </main>
        <QuickLook />
        <TransportBar />
        {toastBanner}
      </div>
    </div>
      )}
    </>
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
