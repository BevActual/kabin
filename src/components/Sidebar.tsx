import { Link, useRouterState } from "@tanstack/react-router";
import {
  BookOpen,
  Film,
  Gamepad2,
  Home,
  Library,
  Music2,
} from "lucide-react";

const libraries = [
  { kind: "game", label: "Games", icon: Gamepad2 },
  { kind: "music", label: "Music", icon: Music2 },
  { kind: "video", label: "Movies", icon: Film },
  { kind: "book", label: "Books", icon: BookOpen },
  { kind: "comic", label: "Comics", icon: Library },
] as const;

export function Sidebar() {
  const pathname = useRouterState({ select: (s) => s.location.pathname });

  return (
    <aside className="kabin-sidebar flex w-[220px] shrink-0 flex-col px-3 py-4">
      <div className="mb-6 px-3">
        <span className="text-[calc(13px*var(--kabin-type-scale))] font-semibold tracking-wide text-kabin-secondary uppercase">
          Kabin
        </span>
      </div>
      <nav className="flex flex-col gap-1">
        <SidebarLink
          to="/"
          label="Home"
          icon={Home}
          active={pathname === "/"}
        />
        <div className="mt-4 mb-2 px-3 text-[calc(12px*var(--kabin-type-scale))] font-medium text-kabin-tertiary">
          Libraries
        </div>
        {libraries.map(({ kind, label, icon: Icon }) => (
          <SidebarLink
            key={kind}
            to="/library/$kind"
            params={{ kind }}
            label={label}
            icon={Icon}
            active={pathname === `/library/${kind}`}
          />
        ))}
      </nav>
    </aside>
  );
}

type SidebarLinkProps = {
  to: string;
  label: string;
  icon: typeof Home;
  active: boolean;
  params?: { kind: string };
};

function SidebarLink({ to, label, icon: Icon, active, params }: SidebarLinkProps) {
  return (
    <Link
      to={to}
      params={params}
      className={`flex items-center gap-3 rounded-[var(--kabin-radius-control)] px-3 py-2 text-[calc(15px*var(--kabin-type-scale))] font-medium transition-colors ${
        active
          ? "bg-kabin-accent/15 text-kabin-accent"
          : "text-kabin-secondary hover:bg-kabin-grouped hover:text-kabin-primary"
      }`}
    >
      <Icon size={20} strokeWidth={1.5} />
      {label}
    </Link>
  );
}
