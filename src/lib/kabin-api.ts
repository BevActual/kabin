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
  biosPaths: Record<string, string>;
  emulation: Record<string, unknown>;
  connectedControllers: string[];
};

export type EmulationPreset = {
  id: string;
  name: string;
  description: string;
};

export type HostStatus = {
  running: boolean;
  enabled: boolean;
  port: number;
  hostName: string;
  fingerprint: string;
  pairingCode: string | null;
  pairingExpiresAt: number | null;
  error: string | null;
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

export type TitleDetails = {
  title: CatalogTitle;
  metaLines: string[];
  isFavorite: boolean;
};

export function toggleFavorite(titleId: string) {
  return invokeOrMock<boolean>("toggle_favorite", { titleId }, false);
}

export function getTitleDetails(titleId: string) {
  return invokeOrMock<TitleDetails | null>(
    "get_title_details",
    { titleId },
    null,
  );
}

export function searchLibrary(query: string, limit?: number) {
  return invokeOrMock<CatalogTitle[]>(
    "search_library",
    { query, limit },
    [],
  );
}

export type RelatedShelf = { heading: string; titles: CatalogTitle[] };

export function getRelatedTitles(titleId: string) {
  return invokeOrMock<RelatedShelf>("get_related_titles", { titleId }, {
    heading: "",
    titles: [],
  });
}

export function remoteGameStreamAvailable() {
  return invokeOrMock<boolean>("remote_game_stream_available", undefined, false);
}

export function startRemoteGameStream(titleId: string) {
  return invokeOrMock<string>("start_remote_game_stream", { titleId });
}

export function stopRemoteGameStream() {
  return invokeOrMock<void>("stop_remote_game_stream", undefined);
}

export function remoteGameStreamStatus() {
  return invokeOrMock<string | null>("remote_game_stream_status", undefined, null);
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
    biosPaths: {},
    emulation: { preset: "balanced" },
    connectedControllers: [],
  });
}

export function listEmulationPresets() {
  return invokeOrMock<EmulationPreset[]>("list_emulation_presets", undefined, []);
}

export function setEmulationPreset(presetId: string) {
  return invokeOrMock<Record<string, unknown>>("set_emulation_preset", {
    presetId,
  });
}

export function setSystemBiosPath(systemId: string, path: string) {
  return invokeOrMock<void>("set_system_bios_path", { systemId, path });
}

export function openExternalPath(path: string) {
  return invokeOrMock<void>("open_external_path", { path });
}

export function setSourceEnabled(key: string, enabled: boolean) {
  return invokeOrMock<void>("set_source_enabled", { key, enabled });
}

export function addMediaDir(path: string, mediaType: string) {
  return invokeOrMock<void>("add_media_dir", { path, mediaType });
}

export function removeMediaDir(path: string) {
  return invokeOrMock<void>("remove_media_dir", { path });
}

export function removeRomDir(path: string) {
  return invokeOrMock<void>("remove_rom_dir", { path });
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

export type ManagedRuntime = { id: string; name: string };

export function recommendedManagedRuntime(systemId: string) {
  return invokeOrMock<ManagedRuntime | null>(
    "recommended_managed_runtime",
    { systemId },
    null,
  );
}

export function installManagedRuntime(runtimeId: string) {
  return invokeOrMock<string>("install_managed_runtime", { runtimeId });
}

export function getHostStatus() {
  return invokeOrMock<HostStatus>("get_host_status", undefined, {
    running: false,
    enabled: false,
    port: 42424,
    hostName: "Kabin",
    fingerprint: "",
    pairingCode: null,
    pairingExpiresAt: null,
    error: null,
  });
}

export function setHostEnabled(enabled: boolean) {
  return invokeOrMock<HostStatus>("set_host_enabled", { enabled });
}

export type DiscoveredHost = {
  name: string;
  address: string;
  port: number;
  tls: boolean;
  fingerprint: string;
};

export type RemoteHostSummary = {
  name: string;
  address: string;
  port: number;
  tls: boolean;
  fingerprint: string;
  paired: boolean;
};

export type PairRemoteHostResult = {
  name: string;
  itemCount: number;
};

export function discoverNearbyKabinHosts() {
  return invokeOrMock<DiscoveredHost[]>("discover_nearby_kabin_hosts", undefined, []);
}

export function listRemoteHosts() {
  return invokeOrMock<RemoteHostSummary[]>("list_remote_hosts", undefined, []);
}

export function pairRemoteHost(host: DiscoveredHost, code: string) {
  return invokeOrMock<PairRemoteHostResult>("pair_remote_host", { host, code });
}

export function removeRemoteHost(name: string) {
  return invokeOrMock<void>("remove_remote_host", { name });
}

export function createHostPairingCode(lifetimeSecs?: number) {
  return invokeOrMock<string>("create_host_pairing_code", {
    lifetimeSecs,
  });
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

export function addRomDirCustom(
  path: string,
  systemId: string,
  commandTemplate: string,
) {
  return invokeOrMock<void>("add_rom_dir_custom", {
    path,
    systemId,
    commandTemplate,
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
