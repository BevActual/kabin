import { invoke } from "@tauri-apps/api/core";
import type { AppInfo, CatalogTitle, HomeShelf } from "../types/catalog";

const isTauri = () =>
  typeof window !== "undefined" &&
  ("__TAURI_INTERNALS__" in window || "__TAURI__" in window);

const mockAppInfo: AppInfo = {
  productName: "Kabin",
  version: "0.1.0-dev",
  configPath: "~/.config/kabin/config.json",
  legacyPython: true,
  windowWidth: 1100,
  windowHeight: 720,
};

const mockShelves: HomeShelf[] = [
  {
    id: "continue",
    label: "Continue",
    titles: [
      {
        id: "demo-1",
        title: "Stellar Drift",
        subtitle: "Resume · 42%",
        kind: "game",
        aspect: "poster",
        progress: 0.42,
        accentHue: 210,
      },
    ],
  },
];

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
  return invokeOrMock<AppInfo>("get_app_info", undefined, mockAppInfo);
}

export function getHomeShelves() {
  return invokeOrMock<HomeShelf[]>("get_home_shelves", undefined, mockShelves);
}

export function getLibraryTitles(kind: string) {
  return invokeOrMock<CatalogTitle[]>(
    "get_library_titles",
    { kind },
    mockShelves.flatMap((s) => s.titles).filter((t) => t.kind === kind),
  );
}
