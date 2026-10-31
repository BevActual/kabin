import { Link, useRouterState } from "@tanstack/react-router";
import { useQuery } from "@tanstack/react-query";
import {
  BookOpen,
  Download,
  Film,
  Gamepad2,
  Heart,
  Home,
  Library,
  Music2,
} from "lucide-react";
import { getDownloadStatus, getLibraryCounts } from "../lib/kabin-api";

const libraries = [
  { kind: "game", label: "Games", icon: Gamepad2 },
  { kind: "music", label: "Music", icon: Music2 },
  { kind: "video", label: "Movies", icon: Film },
  { kind: "book", label: "Books", icon: BookOpen },
  { kind: "comic", label: "Comics", icon: Library },
] as const;

type Props = {
  collapsed: boolean;
};

export function Sidebar({ collapsed }: Props) {
  const pathname = useRouterState({ select: (s) => s.location.pathname });
  const countsQuery = useQuery({
    queryKey: ["libraryCounts"],
    queryFn: getLibraryCounts,
  });
  const downloadsQuery = useQuery({
    queryKey: ["downloads"],
    queryFn: getDownloadStatus,
    refetchInterval: 4000,
  });
  const counts = countsQuery.data ?? {};
  const activeDownloads =
    downloadsQuery.data?.jobs.filter(
      (job) => job.status === "downloading" || job.status === "queued",
    ).length ?? 0;

  return (
    <aside className="kabin-glass kabin-floating-sidebar flex flex-col overflow-hidden py-3">
      {collapsed ? null : (
        <div className="mb-4 px-5 pt-1">
          <span className="text-[calc(17px*var(--kabin-type-scale))] font-semibold tracking-tight text-kabin-primary">
            Kabin
          </span>
        </div>
      )}
      <nav className={`flex flex-col gap-1 ${collapsed ? "px-2" : "px-2.5"}`}>
        <SidebarLink
          to="/"
          label="Home"
          icon={Home}
          collapsed={collapsed}
          active={pathname === "/"}
        />
        <SidebarLink
          to="/library/$kind"
          params={{ kind: "favorites" }}
          label="Favorites"
          icon={Heart}
          collapsed={collapsed}
          badge={counts.favorites ? String(counts.favorites) : undefined}
          active={pathname === "/library/favorites"}
        />
        <SidebarLink
          to="/downloads"
          label="Downloads"
          icon={Download}
          collapsed={collapsed}
          badge={activeDownloads ? String(activeDownloads) : undefined}
          badgeAccent
          active={pathname === "/downloads"}
        />
        {collapsed ? (
          <div className="mx-auto my-3 h-px w-6 bg-kabin-separator" />
        ) : (
          <div className="mt-4 mb-2 px-3 text-[calc(12px*var(--kabin-type-scale))] font-medium text-kabin-tertiary">
            Libraries
          </div>
        )}
        {libraries.map(({ kind, label, icon: Icon }) => {
          const count = counts[kind];
          return (
            <SidebarLink
              key={kind}
              to="/library/$kind"
              params={{ kind }}
              label={label}
              collapsed={collapsed}
              badge={count ? String(count) : undefined}
              icon={Icon}
              active={pathname === `/library/${kind}`}
            />
          );
        })}
      </nav>
    </aside>
  );
}

type SidebarLinkProps = {
  to: string;
  label: string;
  icon: typeof Home;
  active: boolean;
  collapsed: boolean;
  badge?: string;
  badgeAccent?: boolean;
  params?: { kind: string };
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
          ? "kabin-sidebar-active"
          : "text-kabin-secondary hover:bg-[color-mix(in_srgb,var(--kabin-label-primary)_6%,transparent)] hover:text-kabin-primary"
      }`}
    >
      <span className="relative inline-flex">
        <Icon
          size={20}
          strokeWidth={1.5}
          className={active ? "text-kabin-accent" : undefined}
        />
        {collapsed && badge ? (
          <span
            className={`absolute -top-0.5 -right-1 h-1.5 w-1.5 rounded-full ${
              badgeAccent ? "bg-kabin-accent" : "bg-kabin-tertiary"
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
            badgeAccent ? "text-kabin-accent" : "text-kabin-tertiary"
          }`}
        >
          {badge}
        </span>
      ) : null}
    </Link>
  );
}
