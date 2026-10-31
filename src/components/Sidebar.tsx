import { Link, useRouterState } from "@tanstack/react-router";
import { useQuery } from "@tanstack/react-query";
import { ChevronLeft, Download, PanelLeft, Search, Settings, X } from "lucide-react";
import { Fragment, type CSSProperties, type ReactNode, type RefObject } from "react";
import { getDownloadStatus, scanLibrary } from "../lib/kabin-api";
import type { CatalogTitle } from "../types/catalog";
import {
  contentModes,
  getContentMode,
  isInProgress,
  modeIdFromPath,
  sectionGroup,
} from "../lib/modes";
import { gamesInSection } from "../lib/games";
import { musicCount, type MusicShelf } from "../lib/music";
import { seriesTiles } from "../lib/series";
import { collapseShows, isUnwatched } from "../lib/shows";
import {
  downloadSections,
  paneFromPath,
  paneTitle,
  sectionFromHash,
  settingsSections,
  type PaneId,
  type PaneSection,
} from "../lib/panes";
import { useUiStore } from "../store/ui";

type Props = {
  collapsed: boolean;
  searchRef: RefObject<HTMLInputElement | null>;
};

export function Sidebar({ collapsed, searchRef }: Props) {
  const pathname = useRouterState({ select: (s) => s.location.pathname });
  const hash = useRouterState({ select: (s) => s.location.hash });
  const storedMode = useUiStore((s) => s.contentMode);
  const mode = getContentMode(modeIdFromPath(pathname) ?? storedMode);
  const pane = paneFromPath(pathname);
  const title = pane === "library" ? mode.label : paneTitle(pane);

  return (
    <aside className="kabin-glass kabin-floating-sidebar flex flex-col overflow-hidden py-3">
      {collapsed ? (
        <div className="mb-1 flex justify-center">
          <SidebarToggle collapsed />
        </div>
      ) : (
        <div className="flex items-center gap-1 px-3 pt-0.5 pb-3">
          <div className="min-w-0 flex-1 pl-1">
            <div className="text-[calc(11px*var(--kabin-type-scale))] font-medium tracking-wide text-kabin-tertiary">
              Kabin
            </div>
            <div
              key={title}
              className="kabin-page-enter text-[calc(22px*var(--kabin-type-scale))] font-semibold tracking-tight text-[var(--kabin-mode)]"
            >
              {title}
            </div>
          </div>
          <SidebarToggle collapsed={false} />
        </div>
      )}
      {pane === "library" ? (
        <LibraryPane collapsed={collapsed} searchRef={searchRef} />
      ) : (
        <UtilityPane pane={pane} hash={hash} collapsed={collapsed} />
      )}
    </aside>
  );
}

function LibraryPane({
  collapsed,
  searchRef,
}: {
  collapsed: boolean;
  searchRef: RefObject<HTMLInputElement | null>;
}) {
  const pathname = useRouterState({ select: (s) => s.location.pathname });
  const storedMode = useUiStore((s) => s.contentMode);
  const searchQuery = useUiStore((s) => s.searchQuery);
  const setSearchQuery = useUiStore((s) => s.setSearchQuery);
  const setSidebarCollapsed = useUiStore((s) => s.setSidebarCollapsed);
  const mode = getContentMode(modeIdFromPath(pathname) ?? storedMode);
  const scanQuery = useQuery({
    queryKey: ["libraryScan"],
    queryFn: () => scanLibrary(false),
  });
  const downloadsQuery = useQuery({
    queryKey: ["downloads"],
    queryFn: getDownloadStatus,
    refetchInterval: 4000,
  });
  const titles = (scanQuery.data?.titles ?? []).filter((title) =>
    mode.kinds.includes(title.kind),
  );
  const activeDownloads =
    downloadsQuery.data?.jobs.filter(
      (job) => job.status === "downloading" || job.status === "queued",
    ).length ?? 0;

  return (
    <>
      {collapsed ? (
        <button
          type="button"
          aria-label={`Search ${mode.label}`}
          onClick={() => {
            setSidebarCollapsed(false);
            window.setTimeout(() => searchRef.current?.focus(), 0);
          }}
          className="mx-auto mb-2 inline-flex h-9 w-9 items-center justify-center rounded-full text-kabin-secondary hover:bg-[color-mix(in_srgb,var(--kabin-label-primary)_8%,transparent)] hover:text-kabin-primary"
        >
          <Search size={18} strokeWidth={1.5} />
        </button>
      ) : (
        <label className="relative mx-3 mb-3 block">
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
            onChange={(event) => setSearchQuery(event.target.value)}
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
      )}
      <div
        role="tablist"
        aria-label="Media"
        className={
          collapsed
            ? "flex flex-col items-center gap-1 px-2"
            : "mx-3 mb-3 flex items-center gap-0.5 rounded-full bg-[color-mix(in_srgb,var(--kabin-label-primary)_8%,transparent)] p-1"
        }
      >
        {contentModes.map((item) => {
          const Icon = item.icon;
          const selected = item.id === mode.id;
          return (
            <Link
              key={item.id}
              to="/browse/$mode"
              params={{ mode: item.id }}
              role="tab"
              aria-selected={selected}
              title={item.label}
              aria-label={item.label}
              style={{ "--kabin-mode-hue": String(item.hue) } as CSSProperties}
              className={`kabin-mode-swatch inline-flex min-w-0 items-center justify-center rounded-full transition-opacity ${
                collapsed ? "h-9 w-9" : "h-8 flex-1"
              } ${selected ? "" : "opacity-70 hover:opacity-100"}`}
            >
              <Icon size={18} strokeWidth={1.5} />
            </Link>
          );
        })}
      </div>
      <nav
        key={mode.id}
        className={`kabin-page-enter flex min-h-0 flex-1 flex-col gap-1 overflow-y-auto ${
          collapsed ? "px-2" : "px-2.5"
        }`}
      >
        {mode.sections.map((section, index) => {
          const previous = mode.sections[index - 1];
          const split =
            previous != null && sectionGroup(previous) !== sectionGroup(section);
          const active =
            section.id === "home"
              ? pathname === `/browse/${mode.id}`
              : pathname === `/browse/${mode.id}/${section.id}`;
          const count = sectionCount(section.id, section.kinds, titles, section.musicShelf);
          const shown = count > 0 ? String(count) : undefined;
          return (
            <Fragment key={section.id}>
              {split ? <SidebarSplit collapsed={collapsed} /> : null}
              <SidebarLink
                to={section.id === "home" ? "/browse/$mode" : "/browse/$mode/$section"}
                params={
                  section.id === "home"
                    ? { mode: mode.id }
                    : { mode: mode.id, section: section.id }
                }
                label={section.label}
                icon={section.icon}
                collapsed={collapsed}
                active={active}
                badge={shown}
              />
            </Fragment>
          );
        })}
      </nav>
      <SidebarFooter collapsed={collapsed}>
        <SidebarLink
          to="/downloads"
          label="Downloads"
          icon={Download}
          collapsed={collapsed}
          active={false}
          badge={activeDownloads ? String(activeDownloads) : undefined}
          badgeAccent
        />
        <SidebarLink
          to="/settings"
          label="Settings"
          icon={Settings}
          collapsed={collapsed}
          active={false}
        />
      </SidebarFooter>
    </>
  );
}

function UtilityPane({
  pane,
  hash,
  collapsed,
}: {
  pane: Exclude<PaneId, "library">;
  hash: string;
  collapsed: boolean;
}) {
  const storedMode = useUiStore((s) => s.contentMode);
  const mode = getContentMode(storedMode);
  const downloadsQuery = useQuery({
    queryKey: ["downloads"],
    queryFn: getDownloadStatus,
    refetchInterval: 4000,
  });
  const activeDownloads =
    downloadsQuery.data?.jobs.filter(
      (job) => job.status === "downloading" || job.status === "queued",
    ).length ?? 0;
  const wantedCount = downloadsQuery.data?.wanted.length ?? 0;
  const sections = pane === "downloads" ? downloadSections : settingsSections;
  const current = sectionFromHash(sections, hash);

  return (
    <>
      <nav
        key={pane}
        aria-label={paneTitle(pane)}
        className={`kabin-page-enter flex min-h-0 flex-1 flex-col gap-1 overflow-y-auto ${
          collapsed ? "px-2" : "px-2.5"
        }`}
      >
        <SidebarLink
          to="/browse/$mode"
          params={{ mode: mode.id }}
          label={mode.label}
          icon={collapsed ? mode.icon : ChevronLeft}
          collapsed={collapsed}
          active={false}
          ariaLabel={`Back to ${mode.label}`}
        />
        <div className={collapsed ? "mx-auto my-2 h-px w-6 bg-kabin-separator" : "mx-3 my-2 h-px bg-kabin-separator"} />
        {sections.map((section) => (
          <SidebarLink
            key={section.id}
            to={pane === "downloads" ? "/downloads" : "/settings"}
            hash={section.id}
            label={section.label}
            icon={section.icon}
            collapsed={collapsed}
            active={current.id === section.id}
            badge={sectionBadge(pane, section, activeDownloads, wantedCount)}
            badgeAccent={section.id === "activity"}
          />
        ))}
      </nav>
      <SidebarFooter collapsed={collapsed}>
        {pane === "downloads" ? (
          <SidebarLink
            to="/settings"
            label="Settings"
            icon={Settings}
            collapsed={collapsed}
            active={false}
          />
        ) : (
          <SidebarLink
            to="/downloads"
            label="Downloads"
            icon={Download}
            collapsed={collapsed}
            active={false}
            badge={activeDownloads ? String(activeDownloads) : undefined}
            badgeAccent
          />
        )}
      </SidebarFooter>
    </>
  );
}

function sectionBadge(
  pane: PaneId,
  section: PaneSection,
  activeDownloads: number,
  wantedCount: number,
) {
  if (pane === "downloads" && section.id === "activity" && activeDownloads > 0) {
    return String(activeDownloads);
  }
  if (pane === "downloads" && section.id === "wanted" && wantedCount > 0) {
    return String(wantedCount);
  }
  return undefined;
}

function SidebarSplit({ collapsed }: { collapsed: boolean }) {
  return (
    <div
      className={
        collapsed
          ? "mx-auto my-2 h-px w-6 bg-kabin-separator"
          : "mx-3 my-2 h-px bg-kabin-separator"
      }
    />
  );
}

function SidebarFooter({
  collapsed,
  children,
}: {
  collapsed: boolean;
  children: ReactNode;
}) {
  return (
    <div className={collapsed ? "px-2 pt-2" : "px-2.5 pt-2"}>
      {collapsed ? (
        <div className="mx-auto mb-2 h-px w-6 bg-kabin-separator" />
      ) : (
        <div className="mx-3 mb-2 h-px bg-kabin-separator" />
      )}
      {children}
    </div>
  );
}

function SidebarToggle({ collapsed }: { collapsed: boolean }) {
  const toggleSidebar = useUiStore((s) => s.toggleSidebar);
  const label = collapsed ? "Show sidebar" : "Hide sidebar";
  return (
    <button
      type="button"
      onClick={toggleSidebar}
      aria-label={label}
      title={label}
      aria-pressed={!collapsed}
      aria-keyshortcuts="Control+\\"
      className="inline-flex h-8 w-8 shrink-0 items-center justify-center rounded-full text-kabin-secondary transition-colors hover:bg-[color-mix(in_srgb,var(--kabin-label-primary)_8%,transparent)] hover:text-kabin-primary"
    >
      <PanelLeft size={18} strokeWidth={1.5} />
    </button>
  );
}

function sectionCount(
  id: string,
  kinds: string[] | undefined,
  titles: CatalogTitle[],
  shelf?: MusicShelf,
) {
  if (id === "home" || id === "added") return 0;
  if (shelf) return musicCount(titles, shelf);
  if (id === "series") return seriesTiles(titles).length;
  const scoped = kinds
    ? titles.filter((title) => kinds.includes(title.kind))
    : titles;
  if (id === "favorites") return scoped.filter((title) => title.isFavorite).length;
  if (id === "steam" || id === "installed" || id === "consoles" || id === "played") {
    return gamesInSection(scoped, id).length;
  }
  const presented = collapseShows(scoped);
  if (id === "unwatched") return presented.filter(isUnwatched).length;
  if (id === "progress") return presented.filter(isInProgress).length;
  return presented.length;
}

type SidebarLinkProps = {
  to: "/browse/$mode" | "/browse/$mode/$section" | "/downloads" | "/settings";
  label: string;
  icon: typeof Download;
  active: boolean;
  collapsed: boolean;
  badge?: string;
  badgeAccent?: boolean;
  params?: { mode: string; section?: string };
  hash?: string;
  ariaLabel?: string;
};

function SidebarLink({
  to,
  label,
  icon: Icon,
  active,
  collapsed,
  badge,
  badgeAccent,
  params,
  hash,
  ariaLabel,
}: SidebarLinkProps) {
  return (
    <Link
      to={to}
      params={params}
      hash={hash}
      activeOptions={hash ? { includeHash: true, exact: true } : { exact: true }}
      title={ariaLabel ?? label}
      aria-label={ariaLabel ?? (badge ? `${label}, ${badge}` : label)}
      aria-current={active ? "page" : undefined}
      className={`flex items-center rounded-[var(--kabin-radius-control)] text-[calc(15px*var(--kabin-type-scale))] font-medium transition-colors ${
        collapsed ? "justify-center px-0 py-2.5" : "gap-3 px-3 py-2"
      } ${
        active
          ? "kabin-mode-active"
          : "text-kabin-secondary hover:bg-[color-mix(in_srgb,var(--kabin-label-primary)_6%,transparent)] hover:text-kabin-primary"
      }`}
    >
      <span className="relative inline-flex">
        <Icon size={20} strokeWidth={1.5} />
        {collapsed && badge ? (
          <span
            className={`absolute -top-0.5 -right-1 h-1.5 w-1.5 rounded-full ${
              badgeAccent ? "bg-kabin-accent" : "bg-[var(--kabin-mode)]"
            }`}
          />
        ) : null}
      </span>
      {collapsed ? null : (
        <span className="min-w-0 flex-1 truncate">{label}</span>
      )}
      {!collapsed && badge ? (
        <span
          className={`text-[calc(12px*var(--kabin-type-scale))] tabular-nums ${
            badgeAccent ? "text-kabin-accent" : "text-[var(--kabin-mode)]"
          }`}
        >
          {badge}
        </span>
      ) : null}
    </Link>
  );
}
