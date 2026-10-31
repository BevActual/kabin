import { Link, useRouterState } from "@tanstack/react-router";
import { useQuery } from "@tanstack/react-query";
import { Download } from "lucide-react";
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
import {
  downloadSections,
  paneFromPath,
  paneHue,
  sectionFromHash,
  settingsSections,
} from "../lib/panes";
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
  const contentMode = useUiStore((s) => s.contentMode);
  const setContentMode = useUiStore((s) => s.setContentMode);
  const setPreviewTitleId = useUiStore((s) => s.setPreviewTitleId);
  const pathname = useRouterState({ select: (s) => s.location.pathname });
  const hash = useRouterState({ select: (s) => s.location.hash });
  const pane = paneFromPath(pathname);
  const mode = getContentMode(modeIdFromPath(pathname) ?? contentMode);
  const shellHue = paneHue(pane) ?? mode.hue;
  const searching = pane === "library" && searchQuery.trim().length > 0;
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
  }, [pathname, hash, setPreviewTitleId]);
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

  const pageTitle = titleForPath(pathname, hash, searching, mode);

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
      data-pane={pane}
      data-sidebar={sidebarCollapsed ? "collapsed" : "expanded"}
      style={{ "--kabin-mode-hue": String(shellHue) } as CSSProperties}
    >
      <Sidebar collapsed={sidebarCollapsed} searchRef={searchRef} />
      <div className="kabin-content-pane min-w-0">
        {chromeElevated ? (
          <header className="pointer-events-none absolute top-3 left-6 z-20">
            <div className="kabin-glass kabin-glass-strong pointer-events-auto inline-flex max-w-[16rem] items-center px-3 py-1.5">
              <span className="kabin-page-enter truncate text-[calc(15px*var(--kabin-type-scale))] font-semibold tracking-tight">
                {pageTitle}
              </span>
            </div>
          </header>
        ) : null}
        {activeDownloads > 0 ? (
          <div className="pointer-events-none absolute top-3 right-6 z-20">
            <Link
              to="/downloads"
              className="kabin-activity-capsule pointer-events-auto text-[calc(13px*var(--kabin-type-scale))]"
              aria-label={`${activeDownloads} active downloads`}
            >
              <Download size={15} strokeWidth={1.75} />
              {activeDownloads}
            </Link>
          </div>
        ) : null}
        <main
          key={pane === "library" ? pathname : `${pathname}:${pageTitle}`}
          data-chrome={chromeElevated ? "elevated" : "rest"}
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
          {pathname.startsWith("/title/") && !searching ? null : (
            <h1 className="kabin-large-title">{pageTitle}</h1>
          )}
          {searching ? <SearchView /> : children}
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
  hash: string,
  searching: boolean,
  mode: ReturnType<typeof getContentMode>,
) {
  const pane = paneFromPath(pathname);
  if (searching) return "Search";
  if (pane === "downloads") return sectionFromHash(downloadSections, hash).label;
  if (pane === "settings") return sectionFromHash(settingsSections, hash).label;
  if (pathname === `/browse/${mode.id}`) return mode.label;
  const sectionId = pathname.match(/^\/browse\/[^/]+\/([^/]+)/)?.[1];
  if (sectionId) {
    return sectionForMode(mode, sectionId)?.label ?? mode.label;
  }
  if (pathname.startsWith("/title/")) return "Details";
  if (pathname.startsWith("/player/")) return "Now Playing";
  if (pathname.startsWith("/read/")) return "Reader";
  return mode.label;
}
