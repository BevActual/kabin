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
    id: "tv:harbor-lights",
    title: "Harbor Lights",
    subtitle: "Season 1",
    kind: "tv",
    aspect: "widescreen",
    progress: 0.18,
    accentHue: 210,
    addedAt: 5,
    recentAt: 5,
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
];

let sample: LibrarySnapshot | null = null;

function sampleSnapshot(): LibrarySnapshot {
  if (!sample) {
    sample = {
      shelves: [
        { id: "continue-video", label: "Continue", titles: [titles[0]] },
        { id: "added-video", label: "Recently added", titles: [titles[0]] },
        { id: "added-tv", label: "Recently added", titles: [titles[1]] },
        { id: "continue-audiobook", label: "Continue", titles: [titles[3]] },
        { id: "added-book", label: "Recently added", titles: [titles[2]] },
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
