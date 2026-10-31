// Sample shelves for the browser shell when the URL asks for preview=1.
// The desktop app never reads this. It scans real folders.
import type { CatalogTitle, LibrarySnapshot } from "../types/catalog";

const PREVIEW_KEY = "kabin-browser-preview";

const titles: CatalogTitle[] = [
  {
    id: "video:north-station",
    title: "North Station",
    subtitle: "Movie",
    kind: "video",
    aspect: "widescreen",
    progress: 0.42,
    accentHue: 208,
    isFavorite: true,
    addedAt: 6,
    recentAt: 6,
  },
  {
    id: "video:glass-pier",
    title: "Glass Pier",
    subtitle: "Movie",
    kind: "video",
    aspect: "widescreen",
    accentHue: 200,
    addedAt: 7,
  },
  {
    id: "tv:harbor-lights-s01e01",
    title: "The Arrival",
    subtitle: "S1 E1",
    kind: "tv",
    aspect: "widescreen",
    progress: 1,
    accentHue: 210,
    addedAt: 4,
    series: "Harbor Lights",
    seriesIndex: 1001,
  },
  {
    id: "tv:harbor-lights-s01e02",
    title: "The Channel",
    subtitle: "S1 E2",
    kind: "tv",
    aspect: "widescreen",
    progress: 0.4,
    accentHue: 210,
    addedAt: 5,
    recentAt: 8,
    series: "Harbor Lights",
    seriesIndex: 1002,
  },
  {
    id: "tv:harbor-lights-s01e03",
    title: "The Pier",
    subtitle: "S1 E3",
    kind: "tv",
    aspect: "widescreen",
    accentHue: 210,
    addedAt: 8,
    series: "Harbor Lights",
    seriesIndex: 1003,
  },
  {
    id: "book:field-atlas",
    title: "Field Atlas",
    subtitle: "Book",
    kind: "book",
    aspect: "poster",
    accentHue: 38,
    addedAt: 4,
  },
  {
    id: "audiobook:river-notes",
    title: "River Notes",
    subtitle: "Audiobook",
    kind: "audiobook",
    aspect: "square",
    progress: 0.55,
    accentHue: 32,
    addedAt: 3,
  },
  {
    id: "comic:dockside",
    title: "Dockside",
    subtitle: "Comic",
    kind: "comic",
    aspect: "poster",
    accentHue: 28,
    addedAt: 2,
  },
  {
    id: "pdf:workshop-manual",
    title: "Workshop Manual",
    subtitle: "PDF",
    kind: "pdf",
    aspect: "poster",
    accentHue: 24,
    addedAt: 1,
  },
  {
    id: "steam:paper-harbor",
    title: "Paper Harbor",
    subtitle: "Steam",
    kind: "game",
    aspect: "poster",
    accentHue: 200,
    addedAt: 11,
    recentAt: 12,
    playCount: 4,
    playTimeLabel: "3 hours",
  },
  {
    id: "steam:glass-circuit",
    title: "Glass Circuit",
    subtitle: "Steam",
    kind: "game",
    aspect: "poster",
    accentHue: 210,
    addedAt: 10,
  },
  {
    id: "desktop:night-shift",
    title: "Night Shift",
    subtitle: "Installed",
    kind: "game",
    aspect: "poster",
    accentHue: 32,
    addedAt: 9,
    recentAt: 8,
    playCount: 1,
  },
  {
    id: "roms:snes:signal-peak",
    title: "Signal Peak",
    subtitle: "Super Nintendo",
    kind: "game",
    aspect: "poster",
    accentHue: 12,
    addedAt: 7,
  },
  {
    id: "roms:snes:signal-peak-2",
    title: "Signal Peak 2",
    subtitle: "Super Nintendo",
    kind: "game",
    aspect: "poster",
    accentHue: 18,
    addedAt: 6,
  },
  {
    id: "roms:gb:dock-run",
    title: "Dock Run",
    subtitle: "Game Boy",
    kind: "game",
    aspect: "poster",
    accentHue: 140,
    addedAt: 5,
  },
  {
    id: "music:low-tide",
    title: "Low Tide",
    subtitle: "North Line",
    kind: "music",
    aspect: "square",
    album: true,
    trackCount: 4,
    progress: 0.35,
    accentHue: 145,
    recentAt: 9,
    addedAt: 14,
    creators: ["North Line"],
  },
  {
    id: "music:glass-room",
    title: "Glass Room",
    subtitle: "North Line",
    kind: "music",
    aspect: "square",
    album: true,
    trackCount: 3,
    accentHue: 160,
    addedAt: 13,
    creators: ["North Line"],
  },
  {
    id: "music:field-notes",
    title: "Field Notes",
    subtitle: "Dock Choir",
    kind: "music",
    aspect: "square",
    album: true,
    trackCount: 2,
    accentHue: 130,
    addedAt: 12,
    creators: ["Dock Choir"],
  },
  {
    id: "music:river-whistle",
    title: "River Whistle",
    subtitle: "Dock Choir",
    kind: "music",
    aspect: "square",
    accentHue: 120,
    addedAt: 11,
    creators: ["Dock Choir"],
  },
  {
    id: "music:night-market",
    title: "Night Market",
    subtitle: "Song",
    kind: "music",
    aspect: "square",
    accentHue: 100,
    addedAt: 10,
  },
  {
    id: "book:paper-harbor-1",
    title: "The Dock",
    subtitle: "Vol. 1",
    kind: "book",
    aspect: "poster",
    accentHue: 42,
    addedAt: 15,
    series: "Paper Harbor",
    seriesIndex: 1,
  },
  {
    id: "book:paper-harbor-2",
    title: "The Channel",
    subtitle: "Vol. 2",
    kind: "book",
    aspect: "poster",
    progress: 0.35,
    accentHue: 42,
    addedAt: 16,
    recentAt: 4,
    series: "Paper Harbor",
    seriesIndex: 2,
  },
  {
    id: "book:paper-harbor-3",
    title: "The Light",
    subtitle: "Vol. 3",
    kind: "book",
    aspect: "poster",
    accentHue: 42,
    addedAt: 17,
    series: "Paper Harbor",
    seriesIndex: 3,
  },
  {
    id: "comic:tide-glass-1",
    title: "Low Water",
    subtitle: "Vol. 1",
    kind: "comic",
    aspect: "poster",
    accentHue: 200,
    addedAt: 18,
    series: "Tide Glass",
    seriesIndex: 1,
  },
  {
    id: "comic:tide-glass-2",
    title: "High Water",
    subtitle: "Vol. 2",
    kind: "comic",
    aspect: "poster",
    accentHue: 200,
    addedAt: 19,
    series: "Tide Glass",
    seriesIndex: 2,
  },
];

let sample: LibrarySnapshot | null = null;

function sampleSnapshot(): LibrarySnapshot {
  if (!sample) {
    sample = {
      shelves: [
        { id: "continue-video", label: "Continue", titles: [titles[0]] },
        { id: "added-video", label: "Recently added", titles: [titles[1], titles[0]] },
        { id: "continue-tv", label: "Continue", titles: [titles[3]] },
        { id: "added-tv", label: "Recently added", titles: [titles[4], titles[3], titles[2]] },
        { id: "continue-audiobook", label: "Continue", titles: [titles[6]] },
        { id: "added-book", label: "Recently added", titles: [titles[5]] },
        { id: "continue-game", label: "Continue", titles: [titles[9]] },
        { id: "added-game", label: "Recently added", titles: [titles[9], titles[10], titles[11]] },
        { id: "continue-music", label: "Continue", titles: [titles[15]] },
        { id: "added-music", label: "Recently added", titles: [titles[15], titles[16], titles[17]] },
      ],
      titles,
      counts: {},
      errors: [],
      fingerprint: "browser-preview",
    };
  }
  return sample;
}

export function browserSampleSnapshot() {
  if (typeof window === "undefined") return null;
  if ("__TAURI_INTERNALS__" in window || "__TAURI__" in window) return null;
  try {
    const enabled = new URLSearchParams(window.location.search).get("preview") === "1";
    if (enabled) sessionStorage.setItem(PREVIEW_KEY, "1");
    if (sessionStorage.getItem(PREVIEW_KEY) !== "1") return null;
  } catch {
    return null;
  }
  return sampleSnapshot();
}

const albumTracks: Record<string, string[]> = {
  "music:low-tide": ["Hull", "Keel", "Wake", "Harbor"],
  "music:glass-room": ["North Window", "South Window", "Atrium"],
  "music:field-notes": ["Moss", "Fence"],
};

export function previewAlbumTracks(titleId: string) {
  return albumTracks[titleId] ?? [];
}
