import { convertFileSrc, invoke } from "@tauri-apps/api/core";
import type {
  AppInfo,
  CatalogTitle,
  HomeShelf,
  LibrarySnapshot,
} from "../types/catalog";

export type SettingsSnapshot = {
  configPath: string;
  sources: Record<string, boolean | string | number>;
  mediaDirs: unknown[];
  romDirs: unknown[];
};

const isTauri = () =>
  typeof window !== "undefined" &&
  ("__TAURI_INTERNALS__" in window || "__TAURI__" in window);

const emptySnapshot: LibrarySnapshot = {
  shelves: [],
  titles: [],
  counts: {},
  errors: [],
  fingerprint: "",
};

async function invokeOrMock<T>(
  cmd: string,
  args?: Record<string, unknown>,
  fallback?: T,
): Promise<T> {
  if (!isTauri()) {
    if (fallback !== undefined) return fallback;
    throw new Error(`${cmd} requires the Tauri shell (npm run tauri dev)`);
  }
  return invoke<T>(cmd, args);
}

export function getAppInfo() {
  return invokeOrMock<AppInfo>("get_app_info", undefined, {
    productName: "Kabin",
    version: "0.1.0-dev",
    configPath: "~/.config/kabin/config.json",
    legacyPython: true,
    windowWidth: 1100,
    windowHeight: 720,
  });
}

export function scanLibrary(force = false) {
  return invokeOrMock<LibrarySnapshot>(
    "scan_library",
    { force },
    emptySnapshot,
  );
}

export function getHomeShelves() {
  return invokeOrMock<HomeShelf[]>("get_home_shelves", undefined, []);
}

export function getLibraryTitles(kind: string) {
  return invokeOrMock<CatalogTitle[]>("get_library_titles", { kind }, []);
}

export function getTitle(titleId: string) {
  return invokeOrMock<CatalogTitle | null>(
    "get_title",
    { titleId },
    null,
  );
}

export function getLibraryCounts() {
  return invokeOrMock<Record<string, number>>(
    "get_library_counts",
    undefined,
    {},
  );
}

export function launchTitle(titleId: string) {
  return invokeOrMock<void>("launch_title", { titleId });
}

export function getSettings() {
  return invokeOrMock<SettingsSnapshot>("get_settings", undefined, {
    configPath: "~/.config/kabin/config.json",
    sources: {},
    mediaDirs: [],
    romDirs: [],
  });
}

export function setSourceEnabled(key: string, enabled: boolean) {
  return invokeOrMock<void>("set_source_enabled", { key, enabled });
}

export function addMediaDir(path: string, mediaType: string) {
  return invokeOrMock<void>("add_media_dir", { path, mediaType });
}

export function pickFolder() {
  return invokeOrMock<string | null>("pick_folder", undefined, null);
}

export function coverUrl(coverPath?: string | null) {
  if (!coverPath) return null;
  if (!isTauri()) return null;
  try {
    return convertFileSrc(coverPath);
  } catch {
    return null;
  }
}
