import { convertFileSrc, invoke } from "@tauri-apps/api/core";
import type {
  AppInfo,
  CatalogTitle,
  HomeShelf,
  LibrarySnapshot,
} from "../types/catalog";

export type PlaybackTrack = {
  path: string;
  label: string;
};

export type PlaybackSession = {
  titleId: string;
  title: string;
  subtitle: string;
  kind: string;
  tracks: PlaybackTrack[];
  initialTrack: number;
  initialPosition: number;
};

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

export function getPlaybackSession(titleId: string) {
  return invokeOrMock<PlaybackSession | null>(
    "get_playback_session",
    { titleId },
    null,
  );
}

export function savePlaybackProgress(
  titleId: string,
  position: number,
  duration: number,
  track: number,
) {
  return invokeOrMock<void>("save_playback_progress", {
    titleId,
    position,
    duration,
    track,
  });
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

export type ReaderSession = {
  titleId: string;
  title: string;
  backend: string;
  filePath?: string | null;
  pages: string[];
  initialPage: number;
  pageCount: number;
};

export function getReaderSession(titleId: string) {
  return invokeOrMock<ReaderSession | null>(
    "get_reader_session",
    { titleId },
    null,
  );
}

export function saveReaderProgress(
  titleId: string,
  page: number,
  total: number,
  scroll?: number,
) {
  return invokeOrMock<void>("save_reader_progress", {
    titleId,
    page,
    total,
    scroll,
  });
}

export type SystemInfo = { id: string; name: string; extensions: string[] };
export type EmulatorChoice = {
  id: string;
  name: string;
  runtime: string;
  executable: string;
};

export function listSystems() {
  return invokeOrMock<SystemInfo[]>("list_systems", undefined, []);
}

export function listEmulators(systemId: string) {
  return invokeOrMock<EmulatorChoice[]>(
    "list_emulators",
    { systemId },
    [],
  );
}

export function addRomDir(
  path: string,
  systemId: string,
  emulatorId: string,
  executable: string,
  runtime: string,
) {
  return invokeOrMock<void>("add_rom_dir", {
    path,
    systemId,
    emulatorId,
    executable,
    runtime,
  });
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
