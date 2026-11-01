import { convertFileSrc, invoke } from "@tauri-apps/api/core";
import { browserSampleSnapshot, previewAlbumTracks } from "./browser-preview";
import { authorFromLibrary, isAuthorId } from "./authors";
import { artistFromLibrary, isAlbum, isArtistId } from "./music";
import { isSeriesId, seriesFromLibrary } from "./series";
import { episodesForShow, isShowId, showTile } from "./shows";
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

function previewTitles(kind?: string) {
  const titles = browserSampleSnapshot()?.titles ?? [];
  if (!kind) return titles;
  if (kind === "favorites") return titles.filter((title) => title.isFavorite);
  return titles.filter((title) => title.kind === kind);
}

function previewTitle(titleId: string) {
  return previewTitles().find((title) => title.id === titleId) ?? null;
}

function previewPlayback(titleId: string): PlaybackSession | null {
  const title = previewTitle(titleId);
  if (!title) return null;
  if (title.kind !== "music" && title.kind !== "audiobook") return null;
  const labels = title.kind === "music" && isAlbum(title) ? previewAlbumTracks(titleId) : [];
  const tracks =
    labels.length > 0
      ? labels.map((label, index) => ({ path: `preview:${titleId}:${index}`, label }))
      : [{ path: `preview:${titleId}`, label: title.title }];
  return {
    titleId,
    title: title.title,
    subtitle: title.subtitle,
    kind: title.kind,
    tracks,
    initialTrack: 0,
    initialPosition: 2,
  };
}

function previewReader(titleId: string): ReaderSession | null {
  const title = previewTitle(titleId);
  if (!title) return null;
  if (title.kind !== "book" && title.kind !== "comic" && title.kind !== "pdf") return null;
  const pages = [
    `<p style="font:20px Georgia,serif;line-height:1.6">${title.title}</p><p style="font:18px Georgia,serif;line-height:1.6">A sample page, so you can leave the reader and come back to your place.</p>`,
    `<p style="font:18px Georgia,serif;line-height:1.6">Second page of ${title.title}.</p>`,
  ];
  return {
    titleId,
    title: title.title,
    backend: "fb2",
    pages,
    initialPage: 0,
    pageCount: pages.length,
  };
}

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
    browserSampleSnapshot() ?? emptySnapshot,
  );
}

export function getHomeShelves() {
  return invokeOrMock<HomeShelf[]>("get_home_shelves", undefined, []);
}

export function getLibraryTitles(kind: string) {
  return invokeOrMock<CatalogTitle[]>(
    "get_library_titles",
    { kind },
    previewTitles(kind),
  );
}

export async function getTitle(titleId: string) {
  if (isShowId(titleId)) {
    const titles = await getLibraryTitles("tv");
    const episodes = episodesForShow(titles, titleId);
    return episodes.length ? showTile(episodes) : null;
  }
  if (isArtistId(titleId)) {
    const titles = await getLibraryTitles("music");
    return artistFromLibrary(titles, titleId);
  }
  if (isSeriesId(titleId)) {
    const kind = titleId.slice("series:".length).split(":")[0];
    if (!kind) return null;
    const titles = await getLibraryTitles(kind);
    return seriesFromLibrary(titles, titleId);
  }
  if (isAuthorId(titleId)) {
    const lists = await Promise.all(
      ["book", "audiobook", "comic", "pdf"].map((kind) => getLibraryTitles(kind)),
    );
    return authorFromLibrary(lists.flat(), titleId);
  }
  return invokeOrMock<CatalogTitle | null>(
    "get_title",
    { titleId },
    previewTitle(titleId),
  );
}

export type TitleDetails = {
  title: CatalogTitle;
  metaLines: string[];
  isFavorite: boolean;
};

export function toggleFavorite(titleId: string) {
  const title = previewTitle(titleId);
  if (title && !isTauri()) {
    title.isFavorite = !title.isFavorite;
    return Promise.resolve(!!title.isFavorite);
  }
  return invokeOrMock<boolean>("toggle_favorite", { titleId }, false);
}

export function getTitleDetails(titleId: string) {
  const title = previewTitle(titleId);
  return invokeOrMock<TitleDetails | null>(
    "get_title_details",
    { titleId },
    title
      ? { title, metaLines: [], isFavorite: !!title.isFavorite }
      : null,
  );
}

export function searchLibrary(query: string, limit?: number) {
  if (!isTauri()) {
    const needle = query.trim().toLowerCase();
    if (!needle) return Promise.resolve([]);
    const hits = previewTitles().filter((title) =>
      [title.title, title.subtitle, title.series, title.kind, title.id, ...(title.creators ?? [])]
        .filter((part): part is string => !!part)
        .join(" ")
        .toLowerCase()
        .includes(needle),
    );
    return Promise.resolve(hits.slice(0, limit ?? 48));
  }
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
    previewPlayback(titleId),
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
    previewReader(titleId),
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

export type DownloadJob = {
  id: string;
  name: string;
  protocol: string;
  status: string;
  error: string;
  progress: number;
  bytesDone: number;
  bytesTotal: number;
  outputPath: string;
  imported: boolean;
};

export type WantedTitle = {
  id: string;
  title: string;
  year: string;
  kind: string;
  quality: string;
};

export type IndexerSummary = {
  id: string;
  name: string;
  url: string;
  kind: string;
  hasApiKey: boolean;
};

export type DownloadStatus = {
  quality: string;
  importDir: string;
  downloadDir: string;
  connections: number;
  usenet: {
    host: string;
    port: number;
    ssl: boolean;
    username: string;
    hasPassword: boolean;
  };
  indexers: IndexerSummary[];
  wanted: WantedTitle[];
  jobs: DownloadJob[];
};

export type ReleaseHit = {
  title: string;
  sizeBytes: number;
  sizeLabel: string;
  link: string;
  protocol: string;
  indexer: string;
  seeders: number | null;
};

const emptyDownloads: DownloadStatus = {
  quality: "1080p",
  importDir: "",
  downloadDir: "",
  connections: 4,
  usenet: {
    host: "",
    port: 563,
    ssl: true,
    username: "",
    hasPassword: false,
  },
  indexers: [],
  wanted: [],
  jobs: [],
};

export function getDownloadStatus() {
  return invokeOrMock<DownloadStatus>(
    "get_download_status",
    undefined,
    emptyDownloads,
  );
}

export function setDownloadQuality(quality: string) {
  return invokeOrMock<void>("set_download_quality", { quality });
}

export function setDownloadImportDir(path: string) {
  return invokeOrMock<void>("set_download_import_dir", { path });
}

export function setDownloadFolder(path: string) {
  return invokeOrMock<void>("set_download_folder", { path });
}

export function setUsenetConnections(connections: number) {
  return invokeOrMock<void>("set_usenet_connections", { connections });
}

export function saveUsenetServer(server: {
  host: string;
  port: number;
  ssl: boolean;
  username: string;
  password: string;
}) {
  return invokeOrMock<void>("save_usenet_server", { server });
}

export function testUsenetServer() {
  return invokeOrMock<string>("test_usenet_server");
}

export function saveIndexer(indexer: {
  id?: string;
  name: string;
  url: string;
  apiKey: string;
  kind: string;
}) {
  return invokeOrMock<void>("save_indexer", { indexer });
}

export function removeIndexer(id: string) {
  return invokeOrMock<void>("remove_indexer", { id });
}

export function addWanted(title: string, year: string, kind: string) {
  return invokeOrMock<WantedTitle>("add_wanted", { title, year, kind });
}

export function removeWanted(id: string) {
  return invokeOrMock<void>("remove_wanted", { id });
}

export function searchWanted(id: string) {
  return invokeOrMock<ReleaseHit[]>("search_wanted", { id }, []);
}

export function addDownload(
  link: string,
  name: string,
  protocol: string,
  wantedId = "",
) {
  return invokeOrMock<string>("add_download", {
    link,
    name,
    protocol,
    wantedId,
  });
}

export function downloadAction(id: string, action: string) {
  return invokeOrMock<void>("download_action", { id, action });
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
