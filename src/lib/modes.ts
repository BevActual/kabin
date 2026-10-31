import {
  BookOpen,
  CirclePlay,
  Film,
  GalleryVertical,
  Gamepad2,
  Heart,
  Home,
  Library,
  Music2,
  Tv,
  type LucideIcon,
} from "lucide-react";
import type { CatalogTitle, HomeShelf } from "../types/catalog";

export type ContentModeId = "games" | "music" | "movies" | "books" | "comics";

export type ModeSection = {
  id: string;
  label: string;
  icon: LucideIcon;
  kinds?: string[];
};

export type ContentMode = {
  id: ContentModeId;
  label: string;
  kinds: string[];
  hue: number;
  icon: LucideIcon;
  emptyHint: string;
  sections: ModeSection[];
};

export const contentModes: ContentMode[] = [
  {
    id: "games",
    label: "Games",
    kinds: ["game"],
    hue: 32,
    icon: Gamepad2,
    emptyHint: "No games yet. Open Settings to enable Steam or installed apps, then refresh.",
    sections: [
      { id: "home", label: "Home", icon: Home },
      { id: "library", label: "All Games", icon: Library },
      { id: "favorites", label: "Favorites", icon: Heart },
      { id: "progress", label: "In progress", icon: CirclePlay },
    ],
  },
  {
    id: "music",
    label: "Music",
    kinds: ["music"],
    hue: 145,
    icon: Music2,
    emptyHint: "No music yet. Open Settings to add a music folder, then refresh.",
    sections: [
      { id: "home", label: "Home", icon: Home },
      { id: "library", label: "Library", icon: Library },
      { id: "favorites", label: "Favorites", icon: Heart },
      { id: "progress", label: "In progress", icon: CirclePlay },
    ],
  },
  {
    id: "movies",
    label: "Movies",
    kinds: ["video", "tv"],
    hue: 208,
    icon: Film,
    emptyHint: "No movies yet. Open Settings to add a movies or TV folder, then refresh.",
    sections: [
      { id: "home", label: "Home", icon: Home },
      { id: "library", label: "Movies", icon: Film, kinds: ["video"] },
      { id: "shows", label: "TV Shows", icon: Tv, kinds: ["tv"] },
      { id: "favorites", label: "Favorites", icon: Heart },
      { id: "progress", label: "In progress", icon: CirclePlay },
    ],
  },
  {
    id: "books",
    label: "Books",
    kinds: ["book"],
    hue: 38,
    icon: BookOpen,
    emptyHint: "No books yet. Open Settings to add a books folder, then refresh.",
    sections: [
      { id: "home", label: "Home", icon: Home },
      { id: "library", label: "Library", icon: Library },
      { id: "favorites", label: "Favorites", icon: Heart },
      { id: "progress", label: "In progress", icon: CirclePlay },
    ],
  },
  {
    id: "comics",
    label: "Comics",
    kinds: ["comic"],
    hue: 14,
    icon: GalleryVertical,
    emptyHint: "No comics yet. Open Settings to add a comics folder, then refresh.",
    sections: [
      { id: "home", label: "Home", icon: Home },
      { id: "library", label: "Library", icon: Library },
      { id: "favorites", label: "Favorites", icon: Heart },
      { id: "progress", label: "In progress", icon: CirclePlay },
    ],
  },
];

const modeIds = new Set<string>(contentModes.map((mode) => mode.id));

export function isContentModeId(value: string | null | undefined): value is ContentModeId {
  return !!value && modeIds.has(value);
}

export function getContentMode(id: string | null | undefined): ContentMode {
  return contentModes.find((mode) => mode.id === id) ?? contentModes[0];
}

export function modeForKind(kind: string): ContentMode {
  return contentModes.find((mode) => mode.kinds.includes(kind)) ?? contentModes[0];
}

export function modeIdFromPath(pathname: string): ContentModeId | null {
  const match = pathname.match(/^\/browse\/([^/]+)/);
  return isContentModeId(match?.[1]) ? match[1] : null;
}

export function isModeHome(pathname: string): boolean {
  return /^\/browse\/(games|music|movies|books|comics)$/.test(pathname);
}

export function sectionForMode(mode: ContentMode, sectionId: string): ModeSection | null {
  const section = mode.sections.find((item) => item.id === sectionId);
  if (!section || section.id === "home") return null;
  return section;
}

const kindLabel: Record<string, string> = {
  tv: "TV",
  video: "Movies",
  game: "Games",
  music: "Music",
  book: "Books",
  comic: "Comics",
};

function shelfKind(id: string): string | null {
  if (id.startsWith("continue-")) return id.slice("continue-".length);
  if (id.startsWith("added-")) return id.slice("added-".length);
  return null;
}

export function shelvesForMode(shelves: HomeShelf[], mode: ContentMode): HomeShelf[] {
  return shelves.flatMap((shelf) => {
    if (shelf.id === "favorites") {
      const titles = shelf.titles.filter((title) => mode.kinds.includes(title.kind));
      return titles.length ? [{ ...shelf, label: "Favorites", titles }] : [];
    }
    const kind = shelfKind(shelf.id);
    if (!kind || !mode.kinds.includes(kind)) return [];
    const primary = kind === mode.kinds[0];
    const suffix = primary ? "" : ` · ${kindLabel[kind] ?? kind}`;
    const label = shelf.id.startsWith("continue-")
      ? `Continue${suffix}`
      : shelf.id.startsWith("added-")
        ? `Recently added${suffix}`
        : shelf.label;
    return [{ ...shelf, label }];
  });
}

export function isInProgress(title: CatalogTitle) {
  const progress = title.progress ?? 0;
  return progress > 0.01 && progress < 0.98;
}

export function legacyLibraryTarget(
  kind: string,
  fallback: ContentModeId,
): { mode: ContentModeId; section: string } {
  switch (kind) {
    case "game":
      return { mode: "games", section: "library" };
    case "music":
      return { mode: "music", section: "library" };
    case "video":
      return { mode: "movies", section: "library" };
    case "tv":
      return { mode: "movies", section: "shows" };
    case "book":
      return { mode: "books", section: "library" };
    case "comic":
      return { mode: "comics", section: "library" };
    case "favorites":
      return { mode: fallback, section: "favorites" };
    default:
      return { mode: fallback, section: "library" };
  }
}
