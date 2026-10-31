import { Link, useRouterState } from "@tanstack/react-router";
import { useQuery } from "@tanstack/react-query";
import { Download, Search, Settings, X } from "lucide-react";
import type { CSSProperties, RefObject } from "react";
import { getDownloadStatus, scanLibrary } from "../lib/kabin-api";
import type { CatalogTitle } from "../types/catalog";
import {
  contentModes,
  getContentMode,
  isInProgress,
  modeIdFromPath,
} from "../lib/modes";
import { useUiStore } from "../store/ui";

type Props = {
  collapsed: boolean;
  searchRef: RefObject<HTMLInputElement | null>;
};

export function Sidebar({ collapsed, searchRef }: Props) {
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
    <aside className="kabin-glass kabin-floating-sidebar flex flex-col overflow-hidden py-3">
      {collapsed ? null : (
        <div className="px-4 pt-1 pb-3">
          <div className="text-[calc(11px*var(--kabin-type-scale))] font-medium tracking-wide text-kabin-tertiary">
            Kabin
          </div>
          <div
            key={mode.id}
            className="kabin-page-enter text-[calc(22px*var(--kabin-type-scale))] font-semibold tracking-tight text-[var(--kabin-mode)]"
          >
            {mode.label}
          </div>
        </div>
      )}
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
        {mode.sections.map((section) => {
          const active =
            section.id === "home"
              ? pathname === `/browse/${mode.id}`
              : pathname === `/browse/${mode.id}/${section.id}`;
          const count = sectionCount(section.id, section.kinds, titles);
          const shown = count > 0 ? String(count) : undefined;
          return (
            <SidebarLink
              key={section.id}
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
          );
        })}
      </nav>
      <div className={collapsed ? "px-2 pt-2" : "px-2.5 pt-2"}>
        {collapsed ? (
          <div className="mx-auto mb-2 h-px w-6 bg-kabin-separator" />
        ) : (
          <div className="mx-3 mb-2 h-px bg-kabin-separator" />
        )}
        <SidebarLink
          to="/downloads"
          label="Downloads"
          icon={Download}
          collapsed={collapsed}
          active={pathname === "/downloads"}
          badge={activeDownloads ? String(activeDownloads) : undefined}
          badgeAccent
        />
        <SidebarLink
          to="/settings"
          label="Settings"
          icon={Settings}
          collapsed={collapsed}
          active={pathname === "/settings"}
        />
      </div>
    </aside>
  );
}

function sectionCount(
  id: string,
  kinds: string[] | undefined,
  titles: CatalogTitle[],
) {
  if (id === "home") return 0;
  const scoped = kinds
    ? titles.filter((title) => kinds.includes(title.kind))
    : titles;
  if (id === "favorites") return scoped.filter((title) => title.isFavorite).length;
  if (id === "progress") return scoped.filter(isInProgress).length;
  return scoped.length;
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
}: SidebarLinkProps) {
  return (
    <Link
      to={to}
      params={params}
      title={label}
      aria-label={badge ? `${label}, ${badge}` : label}
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
