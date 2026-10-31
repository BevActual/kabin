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
