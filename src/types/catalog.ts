export type TileAspect = "poster" | "square" | "widescreen";

export type CatalogTitle = {
  id: string;
  title: string;
  subtitle: string;
  kind: string;
  aspect: TileAspect;
  progress?: number | null;
  accentHue: number;
};

export type HomeShelf = {
  id: string;
  label: string;
  titles: CatalogTitle[];
};

export type AppInfo = {
  productName: string;
  version: string;
  configPath: string;
  legacyPython: boolean;
  windowWidth: number;
  windowHeight: number;
};
