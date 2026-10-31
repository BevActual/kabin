import {
  AppWindow,
  BookOpen,
  CirclePlay,
  Clapperboard,
  Clock,
  EyeOff,
  FileText,
  Film,
  GalleryVertical,
  Gamepad2,
  Headphones,
  Heart,
  Disc,
  History,
  Home,
  Joystick,
  ListMusic,
  Mic,
  Music2,
  Tv,
  type LucideIcon,
} from "lucide-react";
import type { CatalogTitle, HomeShelf } from "../types/catalog";
import { gameHomeSubtitle, type GameSource } from "./games";
import { musicHomeSubtitle, type MusicShelf } from "./music";
import { collapseShows } from "./shows";

export type ContentModeId = "video" | "books" | "music" | "games";

export type ModeSection = {
  id: string;
  label: string;
  icon: LucideIcon;
  kinds?: string[];
  gameSource?: GameSource;
  musicShelf?: MusicShelf;
  emptyHint?: string;
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
    id: "video",
    label: "Video",
    kinds: ["video", "tv"],
    hue: 208,
    icon: Clapperboard,
    emptyHint:
      "Nothing to watch yet. Open Settings to add a video, movies, or TV folder, then refresh.",
    sections: [
      { id: "home", label: "Home", icon: Home },
      {
        id: "movies",
        label: "Movies",
        icon: Film,
        kinds: ["video"],
        emptyHint:
          "No movies yet. Open Settings to add a movies or video folder, then refresh.",
      },
      {
        id: "tv",
        label: "TV",
        icon: Tv,
        kinds: ["tv"],
        emptyHint: "No TV yet. Open Settings to add a TV or video folder, then refresh.",
      },
      {
        id: "added",
        label: "Recently added",
        icon: Clock,
        emptyHint:
          "Nothing added yet. Open Settings to add a video, movies, or TV folder, then refresh.",
      },
      {
        id: "unwatched",
        label: "Unwatched",
        icon: EyeOff,
        emptyHint: "Nothing waiting. Movies and shows you have not started show up here.",
      },
      { id: "favorites", label: "Favorites", icon: Heart },
      { id: "progress", label: "In progress", icon: CirclePlay },
    ],
  },
  {
    id: "books",
    label: "Books",
    kinds: ["book", "audiobook", "comic", "pdf"],
    hue: 38,
    icon: BookOpen,
    emptyHint:
      "Nothing to read yet. Open Settings to add a books folder, then refresh.",
    sections: [
      { id: "home", label: "Home", icon: Home },
      {
        id: "books",
        label: "Books",
        icon: BookOpen,
        kinds: ["book"],
        emptyHint: "No books yet. Open Settings to add a books folder, then refresh.",
      },
      {
        id: "audiobooks",
        label: "Audiobooks",
        icon: Headphones,
        kinds: ["audiobook"],
        emptyHint:
          "No audiobooks yet. Open Settings to add an audiobooks or books folder, then refresh.",
      },
      {
        id: "comics",
        label: "Comics",
        icon: GalleryVertical,
        kinds: ["comic"],
        emptyHint: "No comics yet. Open Settings to add a comics or books folder, then refresh.",
      },
      {
        id: "pdfs",
        label: "PDFs",
        icon: FileText,
        kinds: ["pdf"],
        emptyHint: "No PDFs yet. Open Settings to add a books folder, then refresh.",
      },
      {
        id: "added",
        label: "Recently added",
        icon: Clock,
        emptyHint: "Nothing added yet. Open Settings to add a books folder, then refresh.",
      },
      {
        id: "unwatched",
        label: "Unread",
        icon: EyeOff,
        emptyHint: "Nothing waiting. Books you have not started show up here.",
      },
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
      {
        id: "albums",
        label: "Albums",
        icon: Disc,
        musicShelf: "albums",
        emptyHint: "No albums yet. Open Settings to add a music folder, then refresh.",
      },
      {
        id: "artists",
        label: "Artists",
        icon: Mic,
        musicShelf: "artists",
        emptyHint: "No artists yet. Open Settings to add a music folder, then refresh.",
      },
      {
        id: "songs",
        label: "Songs",
        icon: ListMusic,
        musicShelf: "songs",
        emptyHint: "No songs yet. Open Settings to add a music folder, then refresh.",
      },
      {
        id: "added",
        label: "Recently added",
        icon: Clock,
        emptyHint: "Nothing added yet. Open Settings to add a music folder, then refresh.",
      },
      { id: "favorites", label: "Favorites", icon: Heart },
      { id: "progress", label: "In progress", icon: CirclePlay },
    ],
  },
  {
    id: "games",
    label: "Games",
    kinds: ["game"],
    hue: 32,
    icon: Gamepad2,
    emptyHint:
      "No games yet. Open Settings to enable Steam, installed apps, or console ROMs, then refresh.",
    sections: [
      { id: "home", label: "Home", icon: Home },
      {
        id: "steam",
        label: "Steam",
        icon: Gamepad2,
        gameSource: "steam",
        emptyHint: "No Steam games yet. Open Settings to enable Steam, then refresh.",
      },
      {
        id: "installed",
        label: "Installed",
        icon: AppWindow,
        gameSource: "installed",
        emptyHint:
          "No installed games yet. Open Settings to enable installed apps, then refresh.",
      },
      {
        id: "consoles",
        label: "Consoles",
        icon: Joystick,
        gameSource: "console",
        emptyHint:
          "No console games yet. Open Settings to add a ROM folder, then refresh.",
      },
      {
        id: "added",
        label: "Recently added",
        icon: Clock,
        emptyHint:
          "Nothing added yet. Open Settings to enable Steam, installed apps, or console ROMs, then refresh.",
      },
      {
        id: "played",
        label: "Recently played",
        icon: History,
        emptyHint: "Nothing played yet. Games you launch show up here.",
      },
      { id: "favorites", label: "Favorites", icon: Heart },
    ],
  },
];

const modeIds = new Set<string>(contentModes.map((mode) => mode.id));

export function isContentModeId(value: string | null | undefined): value is ContentModeId {
  return !!value && modeIds.has(value);
}

export function normalizeContentMode(value: string | null | undefined): ContentModeId {
  if (value === "movies") return "video";
  if (value === "comics") return "books";
  return isContentModeId(value) ? value : "video";
}

export function getContentMode(id: string | null | undefined): ContentMode {
  return contentModes.find((mode) => mode.id === normalizeContentMode(id)) ?? contentModes[0];
}

export function modeForKind(kind: string): ContentMode {
  return contentModes.find((mode) => mode.kinds.includes(kind)) ?? contentModes[0];
}

export function modeIdFromPath(pathname: string): ContentModeId | null {
  const match = pathname.match(/^\/browse\/([^/]+)/);
  return isContentModeId(match?.[1]) ? match[1] : null;
}

export function isModeHome(pathname: string): boolean {
  return /^\/browse\/(video|books|music|games)$/.test(pathname);
}

export function sectionForMode(mode: ContentMode, sectionId: string): ModeSection | null {
  const section = mode.sections.find((item) => item.id === sectionId);
  if (!section || section.id === "home") return null;
  return section;
}

export function sectionGroup(section: ModeSection): "library" | "personal" {
  if (
    section.id === "home" ||
    section.id === "library" ||
    section.kinds?.length ||
    section.gameSource ||
    section.musicShelf
  ) {
    return "library";
  }
  return "personal";
}

const kindLabel: Record<string, string> = {
  tv: "TV",
  video: "Movies",
  game: "Games",
  music: "Music",
  book: "Books",
  audiobook: "Audiobooks",
  comic: "Comics",
  pdf: "PDFs",
};

export function labelForKind(kind: string) {
  return kindLabel[kind] ?? "Title";
}

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
    const titles = shelf.id.startsWith("added-") ? collapseShows(shelf.titles) : shelf.titles;
    const primary = kind === mode.kinds[0];
    const suffix = primary ? "" : ` · ${kindLabel[kind] ?? kind}`;
    const label = shelf.id.startsWith("continue-")
      ? `Continue${suffix}`
      : shelf.id.startsWith("added-")
        ? `Recently added${suffix}`
        : shelf.label;
    return [{ ...shelf, label, titles }];
  });
}

export function homeSubtitle(mode: ContentMode, titles: CatalogTitle[]) {
  if (mode.id === "games") return gameHomeSubtitle(titles);
  if (mode.id === "music") return musicHomeSubtitle(titles);
  const categories = mode.sections.filter((section) => section.kinds?.length);
  if (categories.length === 0) {
    if (titles.length === 0) return mode.label;
    return titles.length === 1 ? "1 title" : `${titles.length} titles`;
  }
  const parts = categories
    .map((section) => {
      const count = collapseShows(
        titles.filter((title) => section.kinds?.includes(title.kind)),
      ).length;
      return count > 0 ? countPhrase(count, section.label) : null;
    })
    .filter((part): part is string => !!part);
  if (parts.length > 0) return parts.join(" · ");
  const labels = categories.map((section) => section.label);
  if (labels.length === 1) return labels[0];
  if (labels.length === 2) return `${labels[0]} and ${labels[1]}`;
  return `${labels.slice(0, -1).join(", ")}, and ${labels[labels.length - 1]}`;
}

function countPhrase(count: number, label: string) {
  if (label === "TV") return count === 1 ? "1 show" : `${count} shows`;
  if (count === 1 && label.endsWith("s")) return `1 ${label.slice(0, -1)}`;
  return `${count} ${label}`;
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
      return { mode: "games", section: "home" };
    case "music":
      return { mode: "music", section: "albums" };
    case "video":
      return { mode: "video", section: "movies" };
    case "tv":
      return { mode: "video", section: "tv" };
    case "book":
      return { mode: "books", section: "books" };
    case "audiobook":
      return { mode: "books", section: "audiobooks" };
    case "comic":
      return { mode: "books", section: "comics" };
    case "pdf":
      return { mode: "books", section: "pdfs" };
    case "favorites":
      return { mode: normalizeContentMode(fallback), section: "favorites" };
    default:
      return { mode: normalizeContentMode(fallback), section: "library" };
  }
}

export const folderTypeLabel: Record<string, string> = {
  screen: "Video",
  video: "Movies",
  tv: "TV",
  book: "Books",
  audiobook: "Audiobooks",
  comic: "Comics",
  pdf: "PDFs",
  music: "Music",
};
