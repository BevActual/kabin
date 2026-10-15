export type TileAspect = "poster" | "square" | "widescreen";

export type CatalogTitle = {
  id: string;
  title: string;
  subtitle: string;
  kind: string;
  aspect: TileAspect;
  progress?: number | null;
  accentHue: number;
  coverPath?: string | null;
  canLaunch?: boolean;
  playCount?: number | null;
  playTimeLabel?: string | null;
};

export type HomeShelf = {
  id: string;
  label: string;
  titles: CatalogTitle[];
};

export type ScanError = {
  source: string;
  message: string;
};

export type LibrarySnapshot = {
  shelves: HomeShelf[];
  titles: CatalogTitle[];
  counts: Record<string, number>;
  errors: ScanError[];
  fingerprint: string;
};

export type AppInfo = {
  productName: string;
  version: string;
  configPath: string;
  legacyPython: boolean;
  windowWidth: number;
  windowHeight: number;
};
